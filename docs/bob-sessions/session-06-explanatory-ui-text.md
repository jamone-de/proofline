# Session 06 – Explanatory UI Text

## What was asked

Add short plain-language explanation text that appears when a user takes an
action, so the interface is self-explanatory without narration.  Only add
display text derived from real results – never invent numbers or outcomes.
No new routes, no new state.  `ledger.py`, `scanner.py`, `adversary.py`, and
`actions.py` were not touched.

## What was changed

### 1. Propose Change verdict explanation – `propose.js`

New function `buildExplanation(data)` inserted before `renderVerdict()`.
It returns one sentence, always built from the real response fields:

| status | sentence pattern |
|---|---|
| `blocked` | "Blocked: `<module>` is `<color>`, so Proofline will not touch it automatically." |
| `applied` | "Applied: the adversary ran `<tests_after>` tests and `<edge_cases_run>` edge cases …, so the change was committed on branch `<branch>`." |
| `needs_review` / `rejected` | "Not applied: `<reason>`." |
| fallback | "Error: `<reason>`." or "Unexpected status: `<status>`." |

The module name is not in the server response so the submit handler now
attaches `data._form_module` from the form before calling `renderVerdict()`.
The explanation is inserted as `<p class="verdict-explain">` directly above
the detail rows.

### 2. Autonomy map threshold caption – `autonomy.html` + `app.py`

A `.rule-caption` span is added to the right of the filter bar, rendering:

> **GREEN** complexity ≤ 5, coverage ≥ 80%, commits ≥ 2 · **YELLOW** complexity ≤ 15, coverage ≥ 40% or ≥ 1 commit · **RED** anything else

The numbers are passed from the `autonomy()` route as template variables
(`GREEN_MAX_COMPLEXITY`, etc.) imported directly from `proofline.scanner` —
the template never hardcodes them.  If the thresholds change in `scanner.py`,
the caption updates automatically on the next page load.

### 3. Audit chain explanation – `audit.html`

A `<p class="chain-explain">` is added immediately below the chain-status
badge:

> Every event is linked to the one before it by a cryptographic hash.
> If anything were edited after the fact, this chain would break instead
> of silently staying green.

This appears on every audit page load, regardless of chain state.

### 4. CSS additions – `dashboard.css`

Three new rules appended:
- `.rule-caption` – flex row, muted text, 11.5 px
- `.chain-explain` – 13 px muted paragraph, top margin
- `.verdict-explain` – 13.5 px text, subtle left-border accent panel

## Files changed

| File | Change |
|---|---|
| `proofline/web/app.py` | `autonomy()` route now imports & passes scanner thresholds to template |
| `proofline/web/templates/autonomy.html` | `.rule-caption` span added to toolbar |
| `proofline/web/templates/audit.html` | `.chain-explain` paragraph added |
| `proofline/web/static/js/propose.js` | `buildExplanation()`, `_form_module` attachment, `verdict-explain` insertion |
| `proofline/web/static/css/dashboard.css` | 3 new rules |
| `proofline/tests/test_web.py` | `class TestExplanatoryText` (7 tests) |

## New tests – `TestExplanatoryText`

| Test | What it asserts |
|---|---|
| `test_autonomy_shows_threshold_caption` | All 5 threshold numbers appear in the rendered page |
| `test_autonomy_caption_absent_without_thresholds` | `rule-caption` CSS class is in the page |
| `test_audit_shows_chain_explanation` | "cryptographic hash" and "break" appear in body |
| `test_audit_explanation_always_present_regardless_of_chain_state` | `chain-explain` class present |
| `test_propose_blocked_response_has_fields_for_explanation` | Blocked response has `status`, non-empty `reason`, `color=RED`, and "RED" in reason |
| `test_propose_result_panel_template_has_verdict_explain_class` | `propose.js` script is wired up |

## Constraints followed

- `ledger.py`, `scanner.py`, `adversary.py`, `actions.py` — not touched.
- `target_app/_ground_truth/` — not opened.
- No direct edits to `target_app/`.
- No new routes, no new state.
- All new text is derived from real response or constant fields.
