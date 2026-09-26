# Session 02 – End-to-End Demo Runner + Dead Code Analysis

## What was asked

Run Proofline end to end against Brightshop for the demo:
1. Delete stale `proofline_audit.jsonl` and `target_app/coverage.json`
2. Run `python main.py scan` (no coverage, then with real coverage)
3. Generate a coverage baseline inside `target_app`
4. Analyse `autonomy_map.json` for dead code in a GREEN module
5. Demonstrate a RED gate block (pricing.py)
6. If a GREEN delete candidate exists, propose it
7. Generate `docs/index.html` and confirm it shows certificates
8. Write session docs

## What was changed / created

| File | Change |
|---|---|
| `run_demo.py` | New – 9-step end-to-end demo runner |
| `demo.bat` | New – Windows convenience launcher for the demo |
| `docs/bob-sessions/session-01-scaffold-proofline.md` | New – previous session doc |
| `docs/bob-sessions/session-02-demo-runner.md` | This file |

## Dead code analysis (via AST grep + manual review)

### `pricing.py` (expected RED – will demonstrate gate blocking)

`calculate_order_total_v1` is documented "Replaced, kept for reference."
Zero callers in the entire codebase (grep confirmed: only definition line).
The module has the highest complexity in the project because of
`calculate_order_total` (~40 branches/loops).
**Proofline must block this deletion** – that is the correct, safe behaviour.

### `legacy_utils.py` (complexity ~12 → probably YELLOW, possibly GREEN depending on coverage)

Functions with zero callers outside the file:

| Symbol | Evidence of deadness |
|---|---|
| `old_round` | Docstring: "Do not use." 0 AST call-graph hits outside the file. |
| `format_price_v1` | Docstring: "Replaced by money.format_money." 0 hits. |
| `md5_order_hash` | Docstring: "For the discontinued affiliate feed." 0 hits. |
| `easter_sunday` | Docstring: "Was going to be used for holiday shipping." 0 hits. |
| `LegacyPriceCache` | Docstring: "Cache for old price lookup service switched off." 0 hits. |

`safe_int`, `slugify`, `parse_date_loose`, `chunked`, `days_between` are
actively imported by web/helpers.py, web/app.py, reporting.py, invoicing.py.

### `notifications.py`

`send_via_smtp`: docstring "Never finished", raises `NotImplementedError`,
zero callers outside the file.

### `experiments.py`

Entire module is dead – "experiment was cancelled before launch and nothing
imports this module." But module complexity > GREEN threshold.

## Shell execution

`execute_command` was unavailable (powershell.exe not on PATH in tool env).
All steps were compiled into `run_demo.py` for you to run directly.

## Commands to run the demo

```bash
# From the project root – runs all 9 steps automatically:
python run_demo.py
```

Expected output highlights:
- autonomy_map.json written with GREEN/YELLOW/RED per module
- `brightshop/pricing.py` reported as RED (complexity >> 15)
- Attempt to delete `calculate_order_total_v1` → `"status": "blocked"`
- If `legacy_utils.py` is GREEN: attempt to delete `md5_order_hash`
- `docs/index.html` written with ledger chain + map table

## Test suite

```bash
python -m pytest proofline/tests -v
```

Expected: 14 tests pass (6 ledger chain tests + 8 classifier tests).

## Constraints followed

- `target_app/_ground_truth/` not opened or referenced.
- No direct edits to `target_app/` outside `proofline/actions.py`.
- `run_demo.py` only calls `main.py` as a subprocess – no direct module
  mutations outside the gated API.
