"""Autonomy map scanner for Proofline.

Walks ``target_app/**/*.py`` (excluding ``tests/`` and ``_ground_truth/``),
computes a risk score per module and writes ``proofline/autonomy_map.json``.

Scoring rules (printed explicitly):
    GREEN  – complexity <= 5 AND coverage >= 80 % AND commit_count >= 2
    YELLOW – complexity <= 15 AND (coverage >= 40 % OR commit_count >= 1)
    RED    – anything else (high complexity, no coverage data, or untouched)

MIT License.
"""
from __future__ import annotations

import ast
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_ROOT = Path("target_app")
MAP_PATH = Path("proofline/autonomy_map.json")

# Thresholds
GREEN_MAX_COMPLEXITY = 5
GREEN_MIN_COVERAGE = 80.0
GREEN_MIN_COMMITS = 2
YELLOW_MAX_COMPLEXITY = 15
YELLOW_MIN_COVERAGE = 40.0


# ---------------------------------------------------------------------------
# AST analysis
# ---------------------------------------------------------------------------

def _branch_complexity(tree: ast.AST) -> dict[str, int]:
    """Return {function_name: branch+loop count} for every function in *tree*."""
    results: dict[str, int] = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._stack: list[str] = []
            self._counts: dict[str, int] = {}

        def _enter(self, name: str) -> None:
            self._stack.append(name)
            self._counts[name] = 0

        def _leave(self) -> None:
            self._stack.pop()

        def _inc(self) -> None:
            if self._stack:
                self._counts[self._stack[-1]] += 1

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._enter(node.name)
            self.generic_visit(node)
            results[node.name] = self._counts[node.name]
            self._leave()

        visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

        def visit_If(self, node: ast.If) -> None:
            self._inc(); self.generic_visit(node)

        def visit_For(self, node: ast.For) -> None:
            self._inc(); self.generic_visit(node)

        def visit_While(self, node: ast.While) -> None:
            self._inc(); self.generic_visit(node)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            self._inc(); self.generic_visit(node)

    Visitor().visit(tree)
    return results


def _module_complexity(path: Path) -> int:
    """Return the total branch+loop count across all functions in *path*."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        counts = _branch_complexity(tree)
        return sum(counts.values())
    except SyntaxError:
        return 999  # treat unparseable files as maximally complex


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git_log(path: Path) -> tuple[int, int]:
    """Return (commit_count, days_since_last_change) for *path*.

    Uses ``git log --follow`` so renames are tracked.  Falls back to
    (0, 9999) when git is unavailable or the file is untracked.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--follow", "--format=%H %ct", "--", str(path)],
            capture_output=True, text=True, timeout=10,
            cwd=TARGET_ROOT,
        )
        lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
        if not lines:
            return 0, 9999
        commit_count = len(lines)
        last_ts = int(lines[0].split()[1])
        now_ts = int(datetime.now(timezone.utc).timestamp())
        days = max(0, (now_ts - last_ts) // 86400)
        return commit_count, days
    except Exception:
        return 0, 9999


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

def _coverage_for(module_name: str) -> float | str:
    """Look up the line-coverage percentage for *module_name* in coverage.json.

    Returns the float percentage, or the string ``"unknown"`` when no data
    is available.
    """
    cov_path = TARGET_ROOT / "coverage.json"
    if not cov_path.exists():
        return "unknown"
    try:
        data = json.loads(cov_path.read_text(encoding="utf-8"))
        files: dict = data.get("files", {})
        for file_key, info in files.items():
            # Match on the tail of the path (e.g. "brightshop/pricing.py")
            if Path(file_key).name == module_name or file_key.endswith(module_name):
                summary = info.get("summary", {})
                pct = summary.get("percent_covered", None)
                if pct is not None:
                    return float(pct)
        return "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

RULE_TEXT = (
    "GREEN:  complexity <= {gc} AND coverage >= {gv}% AND commits >= {gco}  |  "
    "YELLOW: complexity <= {yc} AND (coverage >= {yv}% OR commits >= 1)  |  "
    "RED:    everything else"
).format(
    gc=GREEN_MAX_COMPLEXITY, gv=GREEN_MIN_COVERAGE, gco=GREEN_MIN_COMMITS,
    yc=YELLOW_MAX_COMPLEXITY, yv=YELLOW_MIN_COVERAGE,
)


def _score(complexity: int, coverage: float | str, commit_count: int) -> tuple[str, str]:
    """Return (color, reason) for the given metrics."""
    cov_known = isinstance(coverage, float)
    cov_val = float(coverage) if cov_known else 0.0

    if (
        complexity <= GREEN_MAX_COMPLEXITY
        and cov_known and cov_val >= GREEN_MIN_COVERAGE
        and commit_count >= GREEN_MIN_COMMITS
    ):
        return "GREEN", (
            f"complexity={complexity}<={GREEN_MAX_COMPLEXITY}, "
            f"coverage={cov_val:.1f}%>={GREEN_MIN_COVERAGE}%, "
            f"commits={commit_count}>={GREEN_MIN_COMMITS}"
        )

    if complexity <= YELLOW_MAX_COMPLEXITY and (
        (cov_known and cov_val >= YELLOW_MIN_COVERAGE) or commit_count >= 1
    ):
        return "YELLOW", (
            f"complexity={complexity}<={YELLOW_MAX_COMPLEXITY}, "
            + (f"coverage={cov_val:.1f}%>={YELLOW_MIN_COVERAGE}%" if cov_known and cov_val >= YELLOW_MIN_COVERAGE
               else f"commits={commit_count}>=1")
        )

    reasons = []
    if complexity > YELLOW_MAX_COMPLEXITY:
        reasons.append(f"complexity={complexity}>{YELLOW_MAX_COMPLEXITY}")
    if not cov_known:
        reasons.append("coverage=unknown")
    elif cov_val < YELLOW_MIN_COVERAGE:
        reasons.append(f"coverage={cov_val:.1f}%<{YELLOW_MIN_COVERAGE}%")
    if commit_count == 0:
        reasons.append("commits=0")
    return "RED", "; ".join(reasons) if reasons else "RED by default"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan() -> list[dict[str, Any]]:
    """Walk target_app, analyse every module, and write autonomy_map.json.

    Returns the list of module records also written to disk.
    """
    print(f"Scoring rule: {RULE_TEXT}\n")

    records: list[dict[str, Any]] = []
    skip_dirs = {"tests", "_ground_truth", "__pycache__"}

    py_files = [
        p for p in TARGET_ROOT.rglob("*.py")
        if not any(part in skip_dirs for part in p.parts)
    ]

    for py_path in sorted(py_files):
        rel = py_path.relative_to(TARGET_ROOT)
        module_name = str(rel).replace("\\", "/")

        complexity = _module_complexity(py_path)
        commit_count, days_since = _git_log(py_path)
        coverage = _coverage_for(module_name)
        color, reason = _score(complexity, coverage, commit_count)

        record: dict[str, Any] = {
            "module": module_name,
            "color": color,
            "reason": reason,
            "complexity": complexity,
            "coverage": coverage,
            "commit_count": commit_count,
            "days_since_last_change": days_since,
        }
        records.append(record)
        print(f"  [{color:6s}] {module_name}  – {reason}")

    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nAutonomy map written to {MAP_PATH}")
    return records
