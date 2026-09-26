"""Gated actions for Proofline.

All mutations to ``target_app/`` must go through this module.
Each action checks the autonomy map, optionally runs the adversary,
and applies the change on a dedicated git branch/commit.

Gating rules
------------
* ``propose_delete`` - GREEN modules only.  Verifies the symbol is
  never called (real call-graph check, not grep) before proceeding.
* ``propose_refactor`` - GREEN or YELLOW modules.  YELLOW requires
  ``adversary.run()`` to return ``"accept"``.  RED always returns
  ``"needs_review"`` without writing anything.

MIT License.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import adversary, ledger

TARGET_ROOT = Path("target_app")
MAP_PATH = Path("proofline/autonomy_map.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_map() -> dict[str, dict]:
    """Load the autonomy map keyed by module path."""
    if not MAP_PATH.exists():
        return {}
    records = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    return {r["module"]: r for r in records}


def _color_for(module_path: str) -> str:
    """Return the autonomy color for *module_path*, or ``"RED"`` if unknown."""
    m = _load_map()
    return m.get(module_path, {}).get("color", "RED")


def _is_symbol_called(module_path: str, symbol: str) -> bool:
    """Return True when *symbol* is referenced by name anywhere in target_app.

    Uses a real AST call-graph walk, not grep.  Checks all .py files except
    the declaring module itself and the tests/ / _ground_truth/ directories.
    """
    skip_dirs = {"tests", "_ground_truth", "__pycache__"}
    declaring = TARGET_ROOT / module_path

    for py_path in TARGET_ROOT.rglob("*.py"):
        if any(part in skip_dirs for part in py_path.parts):
            continue
        if py_path.resolve() == declaring.resolve():
            continue
        try:
            tree = ast.parse(py_path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            # Direct call: symbol(...)
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == symbol:
                    return True
                if isinstance(func, ast.Attribute) and func.attr == symbol:
                    return True
            # Name reference (e.g. passed as argument, assigned)
            if isinstance(node, ast.Name) and node.id == symbol:
                return True
    return False


def _git_commit(branch: str, message: str, files: list[Path]) -> bool:
    """Create a git branch, stage *files*, and commit with *message*.

    Returns True on success.
    """
    cwd = TARGET_ROOT

    def _git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + list(args),
            capture_output=True, text=True, cwd=str(cwd),
        )

    # Create and switch to new branch
    _git("checkout", "-b", branch)
    for f in files:
        _git("add", str(f.relative_to(cwd)))
    result = _git("commit", "-m", message)
    # Switch back to the original branch (usually main)
    _git("checkout", "-")
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def propose_delete(module_path: str, symbol: str) -> dict[str, Any]:
    """Propose deleting *symbol* from *module_path*.

    Only allowed for GREEN modules.  Performs a call-graph check first.

    Returns a result dict with ``"status"`` and ``"reason"``.
    """
    ledger.append("actions", "propose_delete", {
        "module": module_path, "symbol": symbol,
    })

    color = _color_for(module_path)
    if color != "GREEN":
        reason = f"Module is {color} - deletions only allowed on GREEN modules."
        ledger.append("actions", "propose_delete_blocked", {
            "module": module_path, "symbol": symbol, "color": color,
        })
        return {"status": "blocked", "reason": reason, "color": color}

    # Call-graph safety check
    if _is_symbol_called(module_path, symbol):
        reason = f"'{symbol}' is still referenced in the codebase; cannot safely delete."
        ledger.append("actions", "propose_delete_blocked", {
            "module": module_path, "symbol": symbol, "reason": "symbol_in_use",
        })
        return {"status": "blocked", "reason": reason, "color": color}

    # Adversary verification
    verdict = adversary.run(module_path, symbol, new_code=None)
    if verdict["verdict"] != "accept":
        return {
            "status": "needs_review",
            "reason": f"Adversary returned '{verdict['verdict']}'.",
            "verdict": verdict,
            "color": color,
        }

    # Apply the deletion on a git branch
    abs_module = TARGET_ROOT / module_path
    branch = f"proofline/delete-{symbol}-{abs_module.stem}"
    branch_message = f"proofline: delete {symbol} from {module_path}"

    # The adversary already restored the original.  We must re-apply the deletion.
    original_src = abs_module.read_text(encoding="utf-8")
    modified_src = adversary._remove_symbol(original_src, symbol)
    abs_module.write_text(modified_src, encoding="utf-8")

    committed = _git_commit(branch, branch_message, [abs_module])

    # Restore working tree
    abs_module.write_text(original_src, encoding="utf-8")

    ledger.append("actions", "propose_delete_applied", {
        "module": module_path, "symbol": symbol,
        "branch": branch, "committed": committed,
    })

    return {
        "status": "applied",
        "reason": f"Deletion committed on branch '{branch}'.",
        "branch": branch,
        "committed": committed,
        "verdict": verdict,
        "color": color,
    }


def propose_refactor(
    module_path: str,
    symbol: str,
    new_code: str,
) -> dict[str, Any]:
    """Propose replacing *symbol* in *module_path* with *new_code*.

    GREEN modules are applied directly after adversary approval.
    YELLOW modules require ``adversary.run()`` to return ``"accept"``.
    RED modules always return ``"needs_review"`` without writing anything.

    Returns a result dict with ``"status"``, ``"reason"``, and
    optionally ``"verdict"`` and ``"branch"``.
    """
    ledger.append("actions", "propose_refactor", {
        "module": module_path, "symbol": symbol,
    })

    color = _color_for(module_path)

    if color == "RED":
        reason = "Module is RED - refactors require manual review."
        ledger.append("actions", "propose_refactor_blocked", {
            "module": module_path, "symbol": symbol, "color": "RED",
        })
        return {"status": "needs_review", "reason": reason, "color": color}

    # Run the adversary for both GREEN and YELLOW
    verdict = adversary.run(module_path, symbol, new_code=new_code)

    if color == "YELLOW" and verdict["verdict"] != "accept":
        reason = (
            f"Module is YELLOW and adversary returned '{verdict['verdict']}'; "
            "change blocked until tests pass."
        )
        ledger.append("actions", "propose_refactor_blocked", {
            "module": module_path, "symbol": symbol,
            "color": "YELLOW", "adversary_verdict": verdict["verdict"],
        })
        return {
            "status": "needs_review",
            "reason": reason,
            "verdict": verdict,
            "color": color,
        }

    if verdict["verdict"] == "reject":
        return {
            "status": "rejected",
            "reason": "Adversary rejected the change (tests failed).",
            "verdict": verdict,
            "color": color,
        }

    # Apply on a git branch
    abs_module = TARGET_ROOT / module_path
    branch = f"proofline/refactor-{symbol}-{abs_module.stem}"
    branch_message = f"proofline: refactor {symbol} in {module_path}"

    original_src = abs_module.read_text(encoding="utf-8")
    modified_src = adversary._replace_symbol(original_src, symbol, new_code)
    abs_module.write_text(modified_src, encoding="utf-8")

    committed = _git_commit(branch, branch_message, [abs_module])

    abs_module.write_text(original_src, encoding="utf-8")

    ledger.append("actions", "propose_refactor_applied", {
        "module": module_path, "symbol": symbol,
        "branch": branch, "committed": committed,
    })

    return {
        "status": "applied",
        "reason": f"Refactor committed on branch '{branch}'.",
        "branch": branch,
        "committed": committed,
        "verdict": verdict,
        "color": color,
    }
