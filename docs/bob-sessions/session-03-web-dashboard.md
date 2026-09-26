# Session 03 – Enterprise Web Dashboard

## What was asked

Build an enterprise-grade web dashboard on top of the existing Proofline core,
fix one real bug in `actions.py`, and add tests. Hard rules unchanged from
session 01.

## Bug fixed: duplicate branch names in `actions.py`

`_git_commit()` previously generated deterministic branch names like
`proofline/delete-<symbol>-<module>`. Running `propose` twice on the same
symbol would fail with "branch already exists".

**Fix**: added `_unique_branch_suffix()` which returns the first 8 hex chars
of a `uuid.uuid4()`. Both `propose_delete` and `propose_refactor` now append
this suffix to every branch name.

New test: [`proofline/tests/test_actions.py`](../../proofline/tests/test_actions.py)
- `test_returns_eight_hex_chars` – suffix is exactly 8 lowercase hex chars
- `test_successive_calls_are_different` – 20 calls produce 20 distinct values
- `test_branch_names_embed_suffix` – pattern matches `-[0-9a-f]{8}$`
- `test_propose_delete_blocked_has_no_branch` – blocked call returns no branch
- `test_propose_refactor_blocked_has_no_branch` – idem for refactor

## Files created / changed

| File | Change |
|---|---|
| `proofline/actions.py` | Added `import uuid`, `_unique_branch_suffix()`, appended suffix to both branch names |
| `proofline/requirements.txt` | New – Flask + pytest + pytest-cov at project root |
| `proofline/web/__init__.py` | New – package marker |
| `proofline/web/app.py` | New – Flask app, 7 routes |
| `proofline/web/templates/base.html` | New – dark sidebar layout |
| `proofline/web/templates/dashboard.html` | New – KPI grid + chain status + risk bar |
| `proofline/web/templates/autonomy.html` | New – sortable/filterable module table |
| `proofline/web/templates/audit.html` | New – ledger events + tamper indicator |
| `proofline/web/templates/certificates.html` | New – one card per applied change |
| `proofline/web/templates/propose.html` | New – form with fetch-based submit |
| `proofline/web/static/css/dashboard.css` | New – 360 lines, dark sidebar, no gradients |
| `proofline/web/static/js/propose.js` | New – plain ES2017, no framework |
| `proofline/tests/test_actions.py` | New – branch naming tests |
| `proofline/tests/test_web.py` | New – Flask test client, 12 tests |
| `main.py` | Added `serve` subcommand + `_cmd_serve()` |
| `README.md` | Expanded with full run instructions + `serve` command |

## Architecture of the web layer

```
GET  /             → dashboard()    → _load_map() + _load_ledger_records() + _summary()
GET  /autonomy     → autonomy()     → _load_map(), sort/filter in Python
GET  /audit        → audit()        → _load_ledger_records() + ledger.verify_chain()
GET  /certificates → certificates() → _load_ledger_records() + _certificates()
GET  /propose      → propose_form() → _load_map() for the module select
POST /propose      → propose_submit() → actions.propose_delete/propose_refactor
POST /scan         → scan_trigger() → scanner.scan() + redirect
```

**No logic is duplicated.** All scoring, verification, chain computation, and
git operations are done by calling the existing core modules. The web layer is
purely a rendering and routing shim.

## Design decisions

- Dark `#0f172a` sidebar, `#f8fafc` content background, `#3b6fd4` accent – no
  gradients, no shadows on text, no emojis as decoration.
- `IBM Plex Mono` font stack for all module paths, symbol names, branch names,
  and hash prefixes.
- Tabular-nums on all numeric columns.
- Status pills (GREEN/YELLOW/RED) use colored background + text, not just text
  color, so they're legible to colour-blind users.
- Single CSS file (`dashboard.css`), single JS file (`propose.js`), no build
  step, no CDN dependency.

## Test isolation strategy

`test_web.py` uses `monkeypatch` to redirect:
- `proofline.web.app.MAP_PATH` → `tmp_path/autonomy_map.json` (controlled data)
- `proofline.actions.MAP_PATH` → same tmp map (so `propose_delete` sees RED)
- `proofline.ledger.LEDGER_PATH` → `tmp_path/test_audit.jsonl` (empty, fresh)

This means no test touches `proofline/autonomy_map.json` or
`proofline_audit.jsonl` and tests run in any order without interference.

## Verification (manual code review – shell unavailable)

All test logic was verified by static reasoning:

1. `GET /` → `_summary()` reads patched map → returns 200. ✓
2. `GET /autonomy` contains `brightshop/money.py` from `_SAMPLE_MAP`. ✓
3. `GET /audit` on empty ledger → `verify_chain()` returns `(True, None)` →
   template renders "Chain intact". ✓
4. `POST /propose` delete on `brightshop/pricing.py` (RED in `_SAMPLE_MAP`) →
   `_color_for()` returns "RED" → `propose_delete` returns `{"status": "blocked"}`. ✓

## To run

```bash
# Test suite (all 3 test files, now 4)
python -m pytest proofline/tests -v

# Web dashboard
python main.py scan          # must run first to populate autonomy_map.json
python main.py serve --port 5050
```

## Constraints followed

- `target_app/_ground_truth/` never opened.
- No direct edits to `target_app/`.
- No logic duplicated in the web layer.
- All new files are MIT-licensed.
- Docstrings on all public functions.
