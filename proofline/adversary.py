"""Adversary - the core verification engine of Proofline.

Runs the target-app pytest suite before and after a proposed change,
generates extra edge-case calls for changed functions, and returns a
structured verdict.

MIT License.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from . import ledger

TARGET_ROOT = Path("target_app")
COVERAGE_JSON = TARGET_ROOT / "coverage.json"

# Edge-case probe values used for every callable parameter
_PROBE_VALUES: list[Any] = [None, 0, -1, 1, "", [], {}, -9999, 9999, 0.0, -0.001, 1000000]


# ---------------------------------------------------------------------------
# Pytest runner
# ---------------------------------------------------------------------------

def _run_pytest(extra_args: list[str] | None = None) -> dict[str, Any]:
    """Run pytest inside target_app and return a result dict.

    Returns ``{passed, failed, errors, total, coverage_pct, raw_output}``.
    """
    cmd = [
        sys.executable, "-m", "pytest",
        "--tb=no", "-q",
        "--cov=brightshop",
        "--cov-report=json:coverage.json",
    ] + (extra_args or [])

    result = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd=str(TARGET_ROOT), timeout=120,
    )
    output = result.stdout + result.stderr

    passed = failed = errors = 0
    for line in output.splitlines():
        # pytest summary line:  "3 passed, 1 failed in 0.12s"
        parts = line.split()
        for i, p in enumerate(parts):
            if p == "passed":
                passed = int(parts[i - 1])
            elif p == "failed":
                failed = int(parts[i - 1])
            elif p == "error" or p == "errors":
                errors = int(parts[i - 1])

    coverage_pct: float | str = "unknown"
    cov_file = TARGET_ROOT / "coverage.json"
    if cov_file.exists():
        try:
            cov_data = json.loads(cov_file.read_text(encoding="utf-8"))
            coverage_pct = cov_data.get("totals", {}).get("percent_covered", "unknown")
        except Exception:
            pass

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": passed + failed + errors,
        "coverage_pct": coverage_pct,
        "raw_output": output[:4000],
        "returncode": result.returncode,
    }


# ---------------------------------------------------------------------------
# Edge-case generation
# ---------------------------------------------------------------------------

def _load_function(module_path: str, symbol: str) -> Any | None:
    """Dynamically load *symbol* from *module_path* relative to TARGET_ROOT.

    Brightshop's own modules use relative imports (from . import config),
    so the file cannot be exec'd standalone, it has to be imported by its
    real dotted name (e.g. brightshop.pricing) so Python sets up the
    package context. Any cached copy is dropped first so this always runs
    the current file on disk, not a version from before the change.

    Returns the callable, or None if loading fails.
    """
    rel = module_path[:-3] if module_path.endswith(".py") else module_path
    dotted = rel.replace("\\", "/").replace("/", ".")

    target_str = str(TARGET_ROOT)
    if target_str not in sys.path:
        sys.path.insert(0, target_str)

    for name in list(sys.modules):
        if name == dotted or name.startswith(dotted + "."):
            del sys.modules[name]

    try:
        mod = importlib.import_module(dotted)
        return getattr(mod, symbol, None)
    except Exception:
        return None


def _generate_edge_cases(fn: Any) -> list[tuple[Any, ...]]:
    """Generate edge-case argument tuples for callable *fn*.

    Inspects the function signature and fills each parameter with every
    probe value, keeping other parameters at their defaults (or None).
    """
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return []

    params = [
        p for p in sig.parameters.values()
        if p.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
    ]
    if not params:
        return [()]  # call with no arguments

    # Build a baseline of defaults / None
    baseline: list[Any] = []
    for p in params:
        if p.default is not inspect.Parameter.empty:
            baseline.append(p.default)
        else:
            baseline.append(None)

    cases: list[tuple[Any, ...]] = []
    for i in range(len(params)):
        for probe in _PROBE_VALUES:
            args = list(baseline)
            args[i] = probe
            cases.append(tuple(args))
    return cases


def _run_edge_cases(fn: Any, cases: list[tuple[Any, ...]]) -> list[dict]:
    """Call *fn* with each case tuple; capture return value or exception."""
    results = []
    for args in cases:
        try:
            ret = fn(*args)
            results.append({"args": list(args), "result": repr(ret), "exception": None})
        except Exception as exc:
            results.append({"args": list(args), "result": None, "exception": repr(exc)})
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(
    module_path: str,
    symbol: str,
    new_code: str | None = None,
) -> dict[str, Any]:
    """Run the full adversarial verification.

    Parameters
    ----------
    module_path:
        Path to the target module relative to ``target_app/``,
        e.g. ``"brightshop/pricing.py"``.
    symbol:
        Name of the function or class being changed / removed.
    new_code:
        The proposed replacement source.  Pass ``None`` for deletions.

    Returns
    -------
    A verdict dict::

        {
            "passed": bool,
            "tests_before": n,
            "tests_after": n,
            "new_edge_cases_run": n,
            "edge_cases_failed": [...],
            "verdict": "accept" | "reject" | "needs_review",
        }
    """
    ledger.append("adversary", "run_start", {
        "module": module_path, "symbol": symbol, "has_new_code": new_code is not None,
    })

    # --- Phase 1: baseline test run ---
    ledger.append("adversary", "pytest_before", {"module": module_path})
    before = _run_pytest()
    ledger.append("adversary", "pytest_before_result", before)

    # --- Phase 2: capture baseline edge-case behaviour ---
    fn_before = _load_function(module_path, symbol)
    edge_before: list[dict] = []
    cases: list[tuple] = []
    if fn_before is not None and callable(fn_before):
        cases = _generate_edge_cases(fn_before)
        edge_before = _run_edge_cases(fn_before, cases)
        ledger.append("adversary", "edge_cases_captured", {
            "symbol": symbol, "count": len(cases),
        })

    # --- Phase 3: apply the change to a temp copy ---
    abs_module = TARGET_ROOT / module_path
    original_src = abs_module.read_text(encoding="utf-8") if abs_module.exists() else ""

    if new_code is None:
        # Deletion: remove the function from the source
        modified_src = _remove_symbol(original_src, symbol)
    else:
        # Refactor: replace the function body
        modified_src = _replace_symbol(original_src, symbol, new_code)

    abs_module.write_text(modified_src, encoding="utf-8")

    try:
        # --- Phase 4: post-change test run ---
        ledger.append("adversary", "pytest_after", {"module": module_path})
        after = _run_pytest()
        ledger.append("adversary", "pytest_after_result", after)

        # --- Phase 5: post-change edge-case comparison ---
        fn_after = _load_function(module_path, symbol)
        edge_after: list[dict] = []
        failed_cases: list[dict] = []
        if fn_after is not None and callable(fn_after) and cases:
            edge_after = _run_edge_cases(fn_after, cases)
            for b, a in zip(edge_before, edge_after):
                if b["result"] != a["result"]:
                    failed_cases.append({
                        "args": b["args"],
                        "before": b["result"],
                        "after": a["result"],
                    })
            ledger.append("adversary", "edge_cases_compared", {
                "symbol": symbol,
                "total": len(cases),
                "failed": len(failed_cases),
            })
    finally:
        # Always restore original source
        abs_module.write_text(original_src, encoding="utf-8")

    # --- Verdict ---
    tests_passed = after["failed"] == 0 and after["errors"] == 0
    edges_ok = len(failed_cases) == 0
    regression = after["passed"] < before["passed"]

    if tests_passed and edges_ok and not regression:
        verdict = "accept"
        passed = True
    elif after["failed"] > 0 or after["errors"] > 0:
        verdict = "reject"
        passed = False
    else:
        verdict = "needs_review"
        passed = False

    result: dict[str, Any] = {
        "passed": passed,
        "tests_before": before["total"],
        "tests_after": after["total"],
        "coverage_before": before["coverage_pct"],
        "coverage_after": after["coverage_pct"],
        "new_edge_cases_run": len(cases),
        "edge_cases_failed": failed_cases,
        "verdict": verdict,
    }
    ledger.append("adversary", "verdict", result)
    return result


# ---------------------------------------------------------------------------
# AST-based source transformations
# ---------------------------------------------------------------------------

def _remove_symbol(src: str, symbol: str) -> str:
    """Return *src* with the top-level function/class *symbol* removed."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    lines = src.splitlines(keepends=True)
    remove_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                start = node.lineno - 1
                end = node.end_lineno  # type: ignore[attr-defined]
                remove_ranges.append((start, end))
    if not remove_ranges:
        return src
    remove_ranges.sort(reverse=True)
    for start, end in remove_ranges:
        del lines[start:end]
    return "".join(lines)


def _replace_symbol(src: str, symbol: str, new_code: str) -> str:
    """Return *src* with the top-level function *symbol* replaced by *new_code*."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    lines = src.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == symbol:
                start = node.lineno - 1
                end = node.end_lineno  # type: ignore[attr-defined]
                replacement = textwrap.dedent(new_code).rstrip() + "\n"
                lines[start:end] = [replacement]
                return "".join(lines)
    # Symbol not found - append the new code
    return src + "\n" + new_code
