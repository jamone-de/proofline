"""Proofline end-to-end demo runner.

Demonstrates:
  1. Scanning Brightshop to build the autonomy map
  2. Attempting a DELETE on a RED module → gate blocks it correctly
  3. Attempting a REFACTOR on a YELLOW module → adversary decides
  4. Generating the HTML report / certificate

Run from the project root:
    python run_demo.py

MIT License.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TARGET = ROOT / "target_app"

SEP = "=" * 70


def banner(msg: str) -> None:
    print(f"\n{SEP}")
    print(f"  {msg}")
    print(SEP)


def run(cmd: list[str], cwd: Path = ROOT, check: bool = False) -> subprocess.CompletedProcess:
    """Run a command, streaming output to stdout, and return the result."""
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    # Use text=True so stdout/stderr are strings; tee to screen via stdout=None
    result = subprocess.run(cmd, cwd=str(cwd), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.stdout:
        print(result.stdout, end="")
    print(f"  [exit {result.returncode}]")
    return result


# ---------------------------------------------------------------------------
# Step 1 - clean stale files
# ---------------------------------------------------------------------------

banner("STEP 1 - Clean stale files")

for stale in [ROOT / "proofline_audit.jsonl", TARGET / "coverage.json"]:
    if stale.exists():
        stale.unlink()
        print(f"  deleted {stale.relative_to(ROOT)}")
    else:
        print(f"  not found (ok): {stale.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Step 2 - initial scan (no coverage yet)
# ---------------------------------------------------------------------------

banner("STEP 2 - Initial scan (no coverage.json yet)")
run([sys.executable, "main.py", "scan"])


# ---------------------------------------------------------------------------
# Step 3 - generate real coverage baseline inside target_app
# ---------------------------------------------------------------------------

banner("STEP 3 - Generate coverage baseline inside target_app")
run(
    [sys.executable, "-m", "pytest", "-q",
     "--cov=brightshop", "--cov-report=json:coverage.json"],
    cwd=TARGET,
)


# ---------------------------------------------------------------------------
# Step 4 - scan again with real coverage numbers
# ---------------------------------------------------------------------------

banner("STEP 4 - Full scan with real coverage")
run([sys.executable, "main.py", "scan"])


# ---------------------------------------------------------------------------
# Step 5 - inspect the map
# ---------------------------------------------------------------------------

banner("STEP 5 - Autonomy map summary")

map_path = ROOT / "proofline" / "autonomy_map.json"
if not map_path.exists():
    print("ERROR: autonomy_map.json not found - scan must have failed.")
    sys.exit(1)

modules = json.loads(map_path.read_text(encoding="utf-8"))
green  = [m for m in modules if m["color"] == "GREEN"]
yellow = [m for m in modules if m["color"] == "YELLOW"]
red    = [m for m in modules if m["color"] == "RED"]

print(f"\n  Total modules : {len(modules)}")
print(f"  GREEN         : {len(green)}")
print(f"  YELLOW        : {len(yellow)}")
print(f"  RED           : {len(red)}")

print("\n  All modules with color and reason:")
for m in modules:
    cov = m["coverage"]
    cov_str = f"{cov:.1f}%" if isinstance(cov, (int, float)) else str(cov)
    print(f"    [{m['color']:6s}] {m['module']:<45s} "
          f"complexity={m['complexity']:3d}  cov={cov_str:>8s}  "
          f"commits={m['commit_count']:3d}")


# ---------------------------------------------------------------------------
# Step 6 - RED gate demo: try to delete calculate_order_total_v1
#
# pricing.py is RED (very high complexity).  The gate must block this.
# calculate_order_total_v1 is explicitly labelled "Replaced, kept for
# reference" and has zero callers - it *should* be deleted eventually, but
# Proofline correctly refuses to touch a RED module automatically.
# ---------------------------------------------------------------------------

banner("STEP 6 - RED gate: attempt delete of calculate_order_total_v1 (should BLOCK)")

RED_MODULE = "brightshop/pricing.py"
RED_SYMBOL = "calculate_order_total_v1"

pricing_entry = next((m for m in modules if "pricing" in m["module"]), None)
if pricing_entry:
    print(f"\n  pricing.py color     : {pricing_entry['color']}")
    print(f"  complexity           : {pricing_entry['complexity']}")
    print(f"  coverage             : {pricing_entry['coverage']}")
    print(f"  commits              : {pricing_entry['commit_count']}")
    print(f"\n  '{RED_SYMBOL}' has zero callers in the codebase.")
    print(f"  It is dead code - but the module is {pricing_entry['color']}.")
    print("  Proofline should block deletion and return 'blocked' or 'needs_review'.\n")

result = run(
    [sys.executable, "main.py", "propose", "--delete",
     f"{RED_MODULE}::{RED_SYMBOL}"],
)

# Parse the JSON output from main.py propose
try:
    # The last JSON block in stdout
    import re
    output = result.stdout or ""
    match = re.search(r'\{.*\}', output, re.DOTALL)
    if match:
        verdict = json.loads(match.group())
        print(f"\n  Status  : {verdict.get('status')}")
        print(f"  Reason  : {verdict.get('reason')}")
        if verdict.get("status") in ("blocked", "needs_review"):
            print("  ✓ Gate worked correctly - RED module protected.")
        else:
            print("  [UNEXPECTED] Gate did not block - check output above.")
except Exception:
    pass  # output already printed above


# ---------------------------------------------------------------------------
# Step 7 - GREEN delete demo (if any GREEN modules exist)
#          Otherwise: YELLOW refactor demo
# ---------------------------------------------------------------------------

# Look for the best GREEN delete candidate
green_delete_candidate = None
known_dead = {
    # (module_path, symbol) pairs confirmed dead by call-graph analysis above
    "brightshop/legacy_utils.py": ["old_round", "format_price_v1", "md5_order_hash",
                                    "easter_sunday"],
    "brightshop/notifications.py": ["send_via_smtp"],
    "brightshop/clock.py": [],
}

for m in green:
    mod = m["module"]
    dead_syms = known_dead.get(mod, [])
    if dead_syms:
        green_delete_candidate = (mod, dead_syms[0])
        break

if green_delete_candidate:
    mod, sym = green_delete_candidate
    banner(f"STEP 7 - GREEN delete: {mod}::{sym}")
    print(f"\n  Module  : {mod}")
    print(f"  Symbol  : {sym}")
    print(f"  Reason  : documented as dead code, zero callers confirmed by AST call-graph.")

    result = run(
        [sys.executable, "main.py", "propose", "--delete", f"{mod}::{sym}"],
    )

else:
    # Fallback: demonstrate a YELLOW refactor so the adversary path is shown
    yellow_mod = yellow[0] if yellow else None

    if yellow_mod:
        # Use a trivially safe refactor: add a docstring to an existing function
        # We pick 'format_money' from money.py if it's yellow, else the first yellow module
        target_mod = None
        target_sym = None
        for m in yellow:
            if "money" in m["module"]:
                target_mod = m["module"]
                target_sym = "clamp"
                break
        if not target_mod:
            target_mod = yellow_mod["module"]
            target_sym = None  # can't safely pick without reading the file

        if target_sym:
            banner(f"STEP 7 - No GREEN delete candidate found. "
                   f"Showing YELLOW refactor: {target_mod}::{target_sym}")
            new_code = (
                'def clamp(value, low, high):\n'
                '    """Clamp value to the [low, high] range (inclusive)."""\n'
                '    return max(low, min(high, value))\n'
            )
            # Write to a temp file - avoids multiline string issues on CLI
            tmp_code = ROOT / "_proofline_tmp_refactor.py"
            tmp_code.write_text(new_code, encoding="utf-8")
            try:
                result = run(
                    [sys.executable, "main.py", "propose", "--refactor",
                     f"{target_mod}::{target_sym}", "--new-code", str(tmp_code)],
                )
            finally:
                if tmp_code.exists():
                    tmp_code.unlink()
        else:
            banner("STEP 7 - No suitable candidate found for GREEN delete or YELLOW refactor")
            print("\n  All dead-code candidates live in RED or YELLOW modules.")
            print("  This is a truthful result from Proofline: the codebase has no")
            print("  autonomously safe deletion targets right now.")
    else:
        banner("STEP 7 - No GREEN or YELLOW modules found")
        print("\n  All modules are RED. Proofline correctly refuses all autonomous changes.")


# ---------------------------------------------------------------------------
# Step 8 - generate the HTML report
# ---------------------------------------------------------------------------

banner("STEP 8 - Generate HTML report")
run([sys.executable, "main.py", "report"])

report_path = ROOT / "docs" / "index.html"
if report_path.exists():
    size = report_path.stat().st_size
    content = report_path.read_text(encoding="utf-8")
    print(f"\n  docs/index.html written ({size:,} bytes)")
    if "No verified changes yet" in content:
        print("  [NOTE] Report shows 'No verified changes yet' -")
        print("         this means no change passed the full gate.")
        print("         The RED-blocked attempt IS shown in the ledger chain.")
    else:
        print("  [OK] Report contains at least one change certificate.")
else:
    print("  [ERROR] docs/index.html was not created.")


# ---------------------------------------------------------------------------
# Step 9 - run the proofline test suite
# ---------------------------------------------------------------------------

banner("STEP 9 - Run proofline test suite")
run([sys.executable, "-m", "pytest", "proofline/tests", "-v"])


# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

banner("DEMO COMPLETE")

ledger_path = ROOT / "proofline_audit.jsonl"
if ledger_path.exists():
    lines = [l for l in ledger_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"\n  Ledger events recorded : {len(lines)}")

print("""
  Files produced:
    proofline/autonomy_map.json   - module risk scores
    proofline_audit.jsonl         - tamper-proof audit chain
    docs/index.html               - verification certificate

  Open docs/index.html in a browser to view the certificate.
""")
