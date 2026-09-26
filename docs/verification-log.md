# Verification log

This file is the human record of what Bob built versus what a human review
found and fixed. It exists because Proofline's whole pitch is "verify before
you trust", so we hold our own process to that standard.

## 2026-09-26: initial scaffold (Bob)

IBM Bob 2.0 built the full `proofline/` package from a single prompt:
`ledger.py`, `scanner.py`, `adversary.py`, `actions.py`, `reporter.py`,
`main.py`, and the test suite in `proofline/tests/`. See
`docs/bob-sessions/` for the session screenshots.

## 2026-09-26: human review found and fixed 3 real bugs

Reviewed and fixed by Adnan, with Claude Code as pair programmer. All three
were confirmed by actually running the code, not by reading it.

1. **Autonomy map was always all-RED.** `scanner.py`'s `_git_log()` ran
   `git log` with `cwd=target_app/` but still passed a path that already
   started with `target_app/`, so it looked for
   `target_app/target_app/brightshop/pricing.py`, which does not exist.
   Every module showed `commits=0`. Fixed by running `git log` from the
   repo root with the path as-is.

2. **Coverage was always "unknown".** `_coverage_for()` compared coverage.json
   keys (which use backslashes on Windows, e.g. `brightshop\pricing.py`)
   against a forward-slash module name. The comparison never matched on
   Windows. Fixed by normalising both sides to forward slashes.

3. **The adversary's edge-case comparison silently never ran.** This is
   the more serious one: `adversary._load_function()` loaded a target
   module with `importlib.util.spec_from_file_location(...)` and executed
   it standalone. Every real Brightshop module uses relative imports
   (`from . import config`), which raise `ImportError: attempted relative
   import with no known parent package` outside a real package context.
   The exception was swallowed by a bare `except Exception: return None`,
   so `adversary.run()` silently fell back to "pytest passed" as its only
   signal, without ever actually comparing before/after behaviour on edge
   cases, the core claim of the tool. Fixed by loading the module by its
   real dotted name (`importlib.import_module("brightshop.pricing")`)
   after registering `target_app/` on `sys.path`, so relative imports
   resolve normally.

Also fixed: a test fixture in `test_scanner.py` whose "complex" synthetic
module did not actually exceed the RED complexity threshold (13 vs. the
required >15), and a Windows console encoding issue where en dashes in
print output rendered as `?` (replaced with plain hyphens throughout).

None of this touched `target_app/_ground_truth/`, which was not read.

## Separately: the demo repository's own git history had to be repaired

`target_app/`'s 75-commit synthetic history was originally brought in with
`git subtree add`, which only rewrites the paths of the merge commit itself,
not the 75 commits behind it. That meant a plain `git log -- target_app/<file>`
from the current branch could not see them, which is exactly what caused
bug 1 above to look like a scanner-only problem at first. Fixed by
re-importing the same history with `git filter-repo --to-subdirectory-filter
target_app`, which bakes the prefix into every commit from the start, then
merging it in with `git merge --allow-unrelated-histories`. Commit dates and
authorship were preserved; only commit hashes changed for that history.
