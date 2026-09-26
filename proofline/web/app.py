"""Flask application for the Proofline web dashboard.

All data comes from the existing core modules, no scoring, verification,
or git logic is duplicated here.  Routes call into proofline.scanner,
proofline.actions, proofline.ledger, and proofline.reporter directly.

MIT License.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for

from proofline import actions, ledger, scanner

# Resolve paths relative to the project root (two levels up from this file)
_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
MAP_PATH = _ROOT / "proofline" / "autonomy_map.json"
TARGET_ROOT = _ROOT / "target_app"


def create_app() -> Flask:
    """Create and configure the Flask application.

    Returns a ready-to-use Flask app instance.
    """
    app = Flask(
        __name__,
        template_folder=str(_HERE / "templates"),
        static_folder=str(_HERE / "static"),
    )
    app.config["SECRET_KEY"] = "proofline-dev"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_map() -> list[dict]:
        """Load autonomy_map.json; return empty list if absent."""
        if not MAP_PATH.exists():
            return []
        return json.loads(MAP_PATH.read_text(encoding="utf-8"))

    def _load_ledger_records() -> list[dict]:
        """Load all ledger records; return empty list if absent."""
        lp = ledger.LEDGER_PATH
        if not lp.exists():
            return []
        records = []
        with lp.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    def _certificates(records: list[dict]) -> list[dict]:
        """Extract applied-change records with their associated adversary verdict."""
        applied = {"propose_delete_applied", "propose_refactor_applied"}
        verdict_actions = {"verdict"}
        verdicts = [r for r in records if r.get("action") in verdict_actions]
        certs = []
        for r in records:
            if r.get("action") not in applied:
                continue
            # Find the most recent verdict preceding this record
            r_ts = r.get("timestamp", "")
            best: dict | None = None
            for v in verdicts:
                if v.get("timestamp", "") <= r_ts:
                    best = v
            certs.append({"change": r, "verdict": best})
        return certs

    def _summary(modules: list[dict], records: list[dict]) -> dict[str, Any]:
        """Build the dashboard summary dict."""
        chain_ok, broken_idx = ledger.verify_chain()
        return {
            "total": len(modules),
            "green": sum(1 for m in modules if m.get("color") == "GREEN"),
            "yellow": sum(1 for m in modules if m.get("color") == "YELLOW"),
            "red": sum(1 for m in modules if m.get("color") == "RED"),
            "changes": sum(
                1 for r in records
                if r.get("action") in {"propose_delete_applied", "propose_refactor_applied"}
            ),
            "events": len(records),
            "chain_ok": chain_ok,
            "broken_idx": broken_idx,
        }

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.route("/")
    def dashboard() -> str:
        """Dashboard overview with summary KPIs."""
        modules = _load_map()
        records = _load_ledger_records()
        s = _summary(modules, records)
        return render_template("dashboard.html", summary=s, active="dashboard")

    @app.route("/autonomy")
    def autonomy() -> str:
        """Sortable, filterable autonomy map table."""
        modules = _load_map()
        color_filter = request.args.get("color", "").upper()
        sort_by = request.args.get("sort", "module")
        sort_dir = request.args.get("dir", "asc")

        if color_filter in ("GREEN", "YELLOW", "RED"):
            modules = [m for m in modules if m.get("color") == color_filter]

        reverse = sort_dir == "desc"
        key_fn: Any
        if sort_by == "complexity":
            key_fn = lambda m: m.get("complexity", 0)
        elif sort_by == "coverage":
            cov = lambda m: (
                m["coverage"] if isinstance(m.get("coverage"), (int, float)) else -1
            )
            key_fn = cov
        elif sort_by == "commits":
            key_fn = lambda m: m.get("commit_count", 0)
        else:
            key_fn = lambda m: m.get("module", "")

        modules = sorted(modules, key=key_fn, reverse=reverse)

        # Pass the real threshold constants so the template never needs to
        # hardcode numbers that live in scanner.py.
        from proofline.scanner import (
            GREEN_MAX_COMPLEXITY, GREEN_MIN_COVERAGE, GREEN_MIN_COMMITS,
            YELLOW_MAX_COMPLEXITY, YELLOW_MIN_COVERAGE,
        )

        return render_template(
            "autonomy.html",
            modules=modules,
            color_filter=color_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
            active="autonomy",
            GREEN_MAX_COMPLEXITY=GREEN_MAX_COMPLEXITY,
            GREEN_MIN_COVERAGE=GREEN_MIN_COVERAGE,
            GREEN_MIN_COMMITS=GREEN_MIN_COMMITS,
            YELLOW_MAX_COMPLEXITY=YELLOW_MAX_COMPLEXITY,
            YELLOW_MIN_COVERAGE=YELLOW_MIN_COVERAGE,
        )

    @app.route("/audit")
    def audit() -> str:
        """Audit chain viewer with tamper indicator."""
        records = _load_ledger_records()
        chain_ok, broken_idx = ledger.verify_chain()
        return render_template(
            "audit.html",
            records=records,
            chain_ok=chain_ok,
            broken_idx=broken_idx,
            active="audit",
        )

    @app.route("/certificates")
    def certificates() -> str:
        """One card per applied change."""
        records = _load_ledger_records()
        certs = _certificates(records)
        return render_template(
            "certificates.html",
            certs=certs,
            active="certificates",
        )

    @app.route("/propose", methods=["GET"])
    def propose_form() -> str:
        """Propose-change form: pick module + symbol, delete or refactor."""
        modules = _load_map()
        return render_template("propose.html", modules=modules, active="propose")

    @app.route("/propose", methods=["POST"])
    def propose_submit():
        """Run the real propose_delete / propose_refactor and return JSON."""
        data = request.get_json(silent=True) or {}
        module_path = (data.get("module") or "").strip()
        symbol = (data.get("symbol") or "").strip()
        action_type = (data.get("action") or "delete").strip()
        new_code = (data.get("new_code") or "").strip()

        if not module_path or not symbol:
            return jsonify({"status": "error", "reason": "module and symbol are required"}), 400

        if action_type == "delete":
            result = actions.propose_delete(module_path, symbol)
        else:
            if not new_code:
                return jsonify({"status": "error", "reason": "new_code required for refactor"}), 400
            result = actions.propose_refactor(module_path, symbol, new_code)

        return jsonify(result)

    @app.route("/source")
    def source_preview():
        """Return the source text of a single function as JSON.

        Query parameters:
            module  – path relative to target_app/ (e.g. ``brightshop/money.py``)
            symbol  – top-level function name to extract

        Returns ``{"source": "..."}`` on success, or
        ``{"error": "..."}`` with HTTP 404 on any failure.

        The file is only *read*, never imported or executed.
        """
        module_param = (request.args.get("module") or "").strip()
        symbol_param = (request.args.get("symbol") or "").strip()

        # --- Input validation ------------------------------------------------
        if not module_param or not symbol_param:
            return jsonify({"error": "module and symbol parameters are required"}), 404

        # Normalise to a Path and reject anything that escapes target_app/
        try:
            candidate = (TARGET_ROOT / module_param).resolve()
        except Exception:
            return jsonify({"error": "invalid module path"}), 404

        try:
            candidate.relative_to(TARGET_ROOT.resolve())
        except ValueError:
            return jsonify({"error": "path escapes target_app/"}), 404

        # Reject _ground_truth/ regardless of resolution
        if "_ground_truth" in candidate.parts:
            return jsonify({"error": "access to _ground_truth/ is not allowed"}), 404

        if not candidate.exists() or not candidate.is_file():
            return jsonify({"error": f"module not found: {module_param}"}), 404

        if candidate.suffix != ".py":
            return jsonify({"error": "only .py files are supported"}), 404

        # --- AST extraction (no import, no exec) -----------------------------
        try:
            source = candidate.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(candidate))
        except (OSError, SyntaxError) as exc:
            return jsonify({"error": f"could not parse file: {exc}"}), 404

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == symbol_param:
                    segment = ast.get_source_segment(source, node)
                    if segment is None:
                        # Fallback: slice by line numbers (Python < 3.8 compat)
                        lines = source.splitlines(keepends=True)
                        start = node.lineno - 1
                        end = node.end_lineno  # type: ignore[attr-defined]
                        segment = "".join(lines[start:end])
                    return jsonify({"source": segment})

        return jsonify({"error": f"symbol '{symbol_param}' not found in {module_param}"}), 404

    @app.route("/scan", methods=["POST"])
    def scan_trigger():
        """Re-run scanner.scan() and redirect to the dashboard."""
        scanner.scan()
        return redirect(url_for("dashboard"))

    return app
