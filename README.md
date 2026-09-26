# Proofline

Cryptographic guardrails, autonomy mapping, and adversarial verification
for autonomous coding agents like IBM Bob.

## What it does

Proofline sits between an AI coding agent and the codebase it wants to change.
Before any edit lands, Proofline:

1. **Maps autonomy risk** — scores every module GREEN / YELLOW / RED based on
   AST complexity, test coverage, and git history.
2. **Gates the change** — GREEN modules can be deleted or refactored; YELLOW
   requires the adversary to pass; RED modules block all automated edits.
3. **Runs adversarial verification** — re-runs the test suite and generates
   edge-case probes before and after the change, comparing results.
4. **Records everything** — a hash-chained audit ledger (JSONL) that is
   tamper-evident: any modification breaks the chain.
5. **Issues a certificate** — a human-readable HTML report with every number
   traceable to a ledger entry or a real pytest run.

## Run

```bash
# Install dependencies (from project root)
pip install -r requirements.txt

# 1. Analyse the codebase
python main.py scan

# 2. (Optional) generate a real coverage baseline first
cd target_app
python -m pytest -q --cov=brightshop --cov-report=json:coverage.json
cd ..
python main.py scan          # re-run with coverage numbers

# 3. Propose a change (CLI)
python main.py propose --delete  brightshop/legacy_utils.py::md5_order_hash
python main.py propose --refactor brightshop/money.py::clamp --new-code new_fn.py

# 4. Generate the HTML certificate
python main.py report        # writes docs/index.html

# 5. Start the web dashboard
python main.py serve --port 5050
# then open http://localhost:5050 in a browser

# 6. Run the test suite
python -m pytest proofline/tests -v
```

## Project layout

```
proofline/
├── __init__.py
├── ledger.py        Hash-chained JSONL flight recorder
├── scanner.py       AST complexity + git log + coverage → autonomy map
├── adversary.py     pytest before/after + edge-case generation
├── actions.py       Gated propose_delete / propose_refactor
├── reporter.py      Generates docs/index.html certificate
├── web/             Flask dashboard (serves on :5050)
│   ├── app.py
│   ├── templates/
│   └── static/
└── tests/           Test suite (pytest)
main.py              CLI entry point
target_app/          The codebase being verified (Brightshop demo app)
```

## License

MIT
