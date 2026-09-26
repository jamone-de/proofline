# Session 05 – Load Current Source Button

## What was asked

Add a "Load current source" button to the Propose Change form that lets a user
doing a real refactor start from the existing implementation, not a blank
textarea.  Read-only addition only – `ledger.py`, `scanner.py`, `adversary.py`,
and `actions.py` were not touched.

## What was built

### 1. New route – `GET /source` in `proofline/web/app.py`

* Reads the file with `Path.read_text()` – no import, no `exec`.
* Parses with `ast.parse()`, walks for the first `FunctionDef` or
  `AsyncFunctionDef` matching the requested symbol name.
* Extracts the exact text with `ast.get_source_segment(source, node)`.
* Returns `{"source": "..."}` on success, `{"error": "..."}` + 404 on any
  failure.

**Security checks (all before any file I/O):**

| Check | Mechanism |
|---|---|
| Path escapes `target_app/` | `candidate.relative_to(TARGET_ROOT.resolve())` – ValueError → 404 |
| Absolute paths (`/etc/passwd`) | Same – resolved path won't be under `target_app/` |
| `_ground_truth/` access | `"_ground_truth" in candidate.parts` explicit check → 404 |
| Non-.py files | `candidate.suffix != ".py"` → 404 |
| File not found | `candidate.exists()` → 404 |
| Parse error | `SyntaxError` caught → 404 |

### 2. `propose.html` template changes

* The `<label>` for the replacement-code textarea is now wrapped in a
  `.textarea-label-row` flex row.
* A `<button id="load-source-btn">` sits at the right end of that row.
* A `<div id="load-source-error">` directly below shows inline errors (no
  browser `alert()`).
* Both the button and the error div are `display:none` by default; JS controls
  visibility.

### 3. `propose.js` changes

* `loadSourceBtn`, `loadSourceErr`, `newCodeInput`, `symbolInput` added to the
  element references at the top.
* New `updateLoadSourceButton()` function: shows the button only when
  `action === "refactor"` AND both module and symbol inputs are non-empty.
  Called from `updateNewCodeVisibility()`, the module `change` listener, and the
  symbol `input` listener.
* New async click handler on `loadSourceBtn`: fetches `GET /source`, fills
  `newCodeInput.value` on success, shows an inline error message on 404.

### 4. `dashboard.css` additions

Three new rules at the end of the file:

* `.textarea-label-row` – flex row between label and button
* `.btn-load-source` – accent-outlined ghost button that fills to solid on hover
* `.load-source-error` – red inline error text below the textarea

### 5. New tests in `proofline/tests/test_web.py` – `class TestSourcePreview`

| Test | What it checks |
|---|---|
| `test_known_symbol_returns_200_and_source` | `clamp` from `money.py` returns 200 and contains `def clamp` |
| `test_known_symbol_source_matches_file` | `round_div` returned source is exact substring of real file |
| `test_unknown_symbol_returns_404` | missing symbol → 404, error contains symbol name |
| `test_missing_params_returns_404` | missing `module` or `symbol` → 404 |
| `test_path_traversal_dotdot_is_rejected` | `../proofline/ledger.py` → 404, error mentions "escapes" or "invalid" |
| `test_absolute_path_traversal_is_rejected` | `/etc/passwd` → 404 |
| `test_ground_truth_path_is_rejected` | `_ground_truth/...` → 404, error mentions `_ground_truth` |
| `test_nonexistent_module_returns_404` | valid-looking but absent path → 404 |

Also removed stale `import tempfile` that was never used in `test_web.py`.

## Files changed

| File | Change |
|---|---|
| `proofline/web/app.py` | +`import ast`, +`TARGET_ROOT`, +`source_preview()` route |
| `proofline/web/templates/propose.html` | `.textarea-label-row` wrapper + load-source button + error div |
| `proofline/web/static/js/propose.js` | new element refs, `updateLoadSourceButton()`, load-source click handler |
| `proofline/web/static/css/dashboard.css` | 3 new CSS rules at end of file |
| `proofline/tests/test_web.py` | `class TestSourcePreview` (8 tests), removed unused `import tempfile` |

## Constraints followed

- `ledger.py`, `scanner.py`, `adversary.py`, `actions.py` — not touched.
- `target_app/_ground_truth/` — not opened, access blocked at the route level.
- No direct edits to `target_app/` outside `actions.py`.
- All new code is MIT-licensed.
- Docstring on `source_preview()`.
