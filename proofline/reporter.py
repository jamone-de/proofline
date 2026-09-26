"""Reporter - generates the Proofline verification certificate.

Reads ``proofline_audit.jsonl``, ``proofline/autonomy_map.json`` and
adversary verdicts embedded in the ledger, then emits ``docs/index.html``.

Every number on the page traces back to a ledger entry or a real
pytest / coverage run.

MIT License.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from . import ledger

LEDGER_PATH = ledger.LEDGER_PATH
MAP_PATH = Path("proofline/autonomy_map.json")
OUT_PATH = Path("docs/index.html")

_COLOR_CSS = {
    "GREEN": "#22c55e",
    "YELLOW": "#eab308",
    "RED": "#ef4444",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_ledger() -> list[dict]:
    """Return all ledger records as a list of dicts."""
    if not LEDGER_PATH.exists():
        return []
    records = []
    with LEDGER_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _load_map() -> list[dict]:
    """Return the autonomy map as a list of module records."""
    if not MAP_PATH.exists():
        return []
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _verdicts_from_ledger(records: list[dict]) -> list[dict]:
    """Extract adversary verdict entries from the ledger."""
    return [r for r in records if r.get("action") == "verdict"]


def _changes_from_ledger(records: list[dict]) -> list[dict]:
    """Extract applied-change entries from the ledger."""
    applied_actions = {"propose_delete_applied", "propose_refactor_applied"}
    return [r for r in records if r.get("action") in applied_actions]


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _esc(text: Any) -> str:
    return html.escape(str(text))


def _badge(color: str, text: str) -> str:
    css = _COLOR_CSS.get(color, "#6b7280")
    return (
        f'<span style="background:{css};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.8em;font-weight:600;">{_esc(text)}</span>'
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_chain_section(records: list[dict], chain_ok: bool, broken_idx: int | None) -> str:
    status_color = "#22c55e" if chain_ok else "#ef4444"
    status_text = "✓ Chain intact" if chain_ok else f"✗ Broken at index {broken_idx}"

    rows = []
    for i, r in enumerate(records):
        row_style = ' style="background:#fff3cd;"' if (not chain_ok and i == broken_idx) else ""
        rows.append(
            f"<tr{row_style}>"
            f"<td>{i}</td>"
            f"<td>{_esc(r.get('timestamp',''))}</td>"
            f"<td>{_esc(r.get('actor',''))}</td>"
            f"<td>{_esc(r.get('action',''))}</td>"
            f"<td style='font-family:monospace;font-size:0.75em;'>"
            f"{_esc(r.get('hash','')[:16])}…</td>"
            f"</tr>"
        )

    rows_html = "\n".join(rows)
    return f"""
<section>
  <h2>Audit Chain
    <span style="float:right;color:{status_color};font-size:0.85em;">{status_text}</span>
  </h2>
  <table>
    <thead><tr>
      <th>#</th><th>Timestamp</th><th>Actor</th><th>Action</th><th>Hash (prefix)</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</section>
"""


def _build_map_section(modules: list[dict]) -> str:
    rows = []
    for m in modules:
        color = m.get("color", "RED")
        cov = m.get("coverage", "unknown")
        cov_str = f"{cov:.1f}%" if isinstance(cov, (int, float)) else str(cov)
        rows.append(
            f"<tr>"
            f"<td>{_badge(color, color)}</td>"
            f"<td style='font-family:monospace;'>{_esc(m.get('module',''))}</td>"
            f"<td>{_esc(m.get('complexity',''))}</td>"
            f"<td>{_esc(cov_str)}</td>"
            f"<td>{_esc(m.get('commit_count',''))}</td>"
            f"<td style='font-size:0.85em;color:#555;'>{_esc(m.get('reason',''))}</td>"
            f"</tr>"
        )
    rows_html = "\n".join(rows)
    return f"""
<section>
  <h2>Autonomy Map</h2>
  <table>
    <thead><tr>
      <th>Risk</th><th>Module</th><th>Complexity</th>
      <th>Coverage</th><th>Commits</th><th>Reason</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</section>
"""


def _build_certificates(changes: list[dict], verdicts: list[dict]) -> str:
    if not changes:
        return "<section><h2>Change Certificates</h2><p>No verified changes yet.</p></section>"

    # Index verdicts by rough position (they appear just after the run)
    cards = []
    for ch in changes:
        d = ch.get("details", {})
        module = d.get("module", "?")
        symbol = d.get("symbol", "?")
        branch = d.get("branch", "?")
        committed = d.get("committed", False)

        # Find the most recent verdict before this change entry
        matching_verdict: dict | None = None
        for v in verdicts:
            vd = v.get("details", {})
            if "verdict" in vd:
                matching_verdict = vd

        vdict = matching_verdict or {}
        verdict_color = {"accept": "GREEN", "reject": "RED", "needs_review": "YELLOW"}.get(
            vdict.get("verdict", ""), "YELLOW"
        )

        risks: list[str] = []
        if vdict.get("edge_cases_failed"):
            risks.append(f"{len(vdict['edge_cases_failed'])} edge-case(s) differed")
        if not vdict.get("passed"):
            risks.append("adversary did not pass")

        risk_html = (
            "<ul>" + "".join(f"<li>{_esc(r)}</li>" for r in risks) + "</ul>"
            if risks else "<p style='color:#22c55e;'>No known risks.</p>"
        )

        cards.append(f"""
<div style="border:1px solid #e5e7eb;border-radius:6px;padding:1em 1.2em;margin-bottom:1em;">
  <h3 style="margin:0 0 0.4em;">{_esc(action_label(ch.get('action','')))} -
    <code>{_esc(symbol)}</code> in <code>{_esc(module)}</code>
    {_badge(verdict_color, vdict.get('verdict','?').upper())}
  </h3>
  <table style="font-size:0.9em;">
    <tr><td>Branch</td><td><code>{_esc(branch)}</code></td></tr>
    <tr><td>Committed</td><td>{_esc(committed)}</td></tr>
    <tr><td>Tests before / after</td>
        <td>{_esc(vdict.get('tests_before','?'))} / {_esc(vdict.get('tests_after','?'))}</td></tr>
    <tr><td>Coverage before / after</td>
        <td>{_esc(vdict.get('coverage_before','?'))} / {_esc(vdict.get('coverage_after','?'))}</td></tr>
    <tr><td>Edge cases run</td><td>{_esc(vdict.get('new_edge_cases_run','?'))}</td></tr>
  </table>
  <h4>Known risks</h4>{risk_html}
  <p style="font-size:0.78em;color:#888;">
    Ledger timestamp: {_esc(ch.get('timestamp','?'))}
    · Hash: <code>{_esc(ch.get('hash','')[:32])}…</code>
  </p>
</div>""")

    return "<section><h2>Change Certificates</h2>" + "\n".join(cards) + "</section>"


def action_label(action: str) -> str:
    """Return a human-readable label for a ledger action key."""
    labels = {
        "propose_delete_applied": "Delete",
        "propose_refactor_applied": "Refactor",
    }
    return labels.get(action, action)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate() -> Path:
    """Read ledger + map, produce ``docs/index.html`` and return its path."""
    records = _load_ledger()
    modules = _load_map()
    chain_ok, broken_idx = ledger.verify_chain()
    verdicts = _verdicts_from_ledger(records)
    changes = _changes_from_ledger(records)

    total = len(modules)
    green = sum(1 for m in modules if m.get("color") == "GREEN")
    yellow = sum(1 for m in modules if m.get("color") == "YELLOW")
    red = sum(1 for m in modules if m.get("color") == "RED")

    summary_html = f"""
<div style="display:flex;gap:2em;margin-bottom:1.5em;flex-wrap:wrap;">
  <div class="card"><div class="big">{total}</div><div>Modules scanned</div></div>
  <div class="card" style="border-color:#22c55e;"><div class="big" style="color:#22c55e;">{green}</div><div>GREEN</div></div>
  <div class="card" style="border-color:#eab308;"><div class="big" style="color:#eab308;">{yellow}</div><div>YELLOW</div></div>
  <div class="card" style="border-color:#ef4444;"><div class="big" style="color:#ef4444;">{red}</div><div>RED</div></div>
  <div class="card"><div class="big">{len(changes)}</div><div>Changes applied</div></div>
  <div class="card"><div class="big">{len(records)}</div><div>Ledger events</div></div>
</div>
"""

    html_body = (
        summary_html
        + _build_map_section(modules)
        + _build_chain_section(records, chain_ok, broken_idx)
        + _build_certificates(changes, verdicts)
    )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Proofline - Verification Certificate</title>
<style>
  body {{font-family:-apple-system,"Segoe UI",system-ui,sans-serif;
         max-width:960px;margin:2em auto;padding:0 1em;
         color:#1f2328;background:#fff;line-height:1.6;}}
  h1 {{color:#1f2328;border-bottom:2px solid #3b82d4;padding-bottom:0.3em;}}
  h2 {{color:#1f2328;margin-top:2em;}}
  table {{border-collapse:collapse;width:100%;font-size:0.9em;}}
  th,td {{border:1px solid #e5e7eb;padding:0.4em 0.7em;text-align:left;}}
  th {{background:#f7f8fa;font-weight:600;}}
  tr:hover {{background:#f7f8fa;}}
  section {{margin-bottom:2.5em;}}
  .card {{border:1px solid #e5e7eb;border-radius:6px;padding:0.8em 1.2em;
          min-width:110px;text-align:center;background:#f7f8fa;}}
  .big {{font-size:2em;font-weight:700;}}
  code {{background:#f1f5f9;padding:1px 4px;border-radius:3px;font-size:0.9em;}}
  footer {{border-top:1px solid #e5e7eb;margin-top:3em;padding-top:0.8em;
           text-align:center;font-size:0.75em;color:#57606a;}}
</style>
</head>
<body>
<h1>Proofline - Verification Certificate</h1>
{html_body}
<footer>Made with IBM Bob</footer>
</body>
</html>"""

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(page, encoding="utf-8")
    print(f"Certificate written to {OUT_PATH}")
    return OUT_PATH
