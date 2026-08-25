# Brightshop

A fictional online shop back office. **The code is intentionally messy.** It exists as a realistic, deliberately "legacy" target for tools that read, refactor and clean up code, for example an AI agent that removes dead code and verifies its own changes.

- Python 3.11+ (developed on 3.13), Flask, no database, no network, no secrets.
- Business logic lives in the `brightshop/` package, the Flask admin UI in `brightshop/web/`.
- Fully deterministic: seed data comes from a tiny LCG, the "current" date is fixed to **2026-09-15** (override with `BRIGHTSHOP_TODAY` or `--today`). Nothing reads the wall clock, so before/after behaviour can be compared automatically.

> **Important:** the folder `_ground_truth/` contains the answer key (every dead function, every hidden business rule, the intended green/yellow/red module ranking) and a behaviour snapshot. **Do not feed `_ground_truth/` to the tool you are testing.** Exclude it from any scan or copy it away first.

## What is in the box

| Screen | Path |
|---|---|
| Dashboard (KPIs, weekly revenue, needs attention, recent orders) | `/` |
| Orders list and order detail (with customer e-mail preview) | `/orders`, `/orders/<id>` |
| Invoice and credit note view, print friendly | `/invoices/<number>` |
| Price calculator (cart, customer, coupon, points, date, return mode) | `/calculator` |
| Customers and customer detail | `/customers`, `/customers/<id>` |
| Reports (sales by month/week/day/category/country/customer, CSV and JSON export) | `/reports` |
| Inventory and reorder suggestions | `/inventory` |
| JSON: `POST /api/calculate`, `GET /api/kpis`, `GET /api/invoices/<number>`, `GET /healthz` | |

The UI has a light and a dark theme (follows the OS, toggle in the top bar) and works down to phone width.

## Install

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1      Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
```

## Run

```bash
python -m brightshop            # http://127.0.0.1:5590
python -m brightshop --port 8000 --today 2026-09-15
```

On Windows you can also double-click `start.bat` (creates the venv on first run).

## Test and coverage

```bash
pytest
pytest --cov=brightshop --cov-report=term-missing
```

The suite is small and passes. It covers roughly a fifth of the statements, unevenly on purpose (some modules 0 %, some 60 to 100 %).

## Behaviour snapshot (golden master)

```bash
python _ground_truth/snapshot.py --check     # compare current behaviour with the stored snapshot
python _ground_truth/snapshot.py --write     # regenerate it (only when you intend to change behaviour)
```

The snapshot runs about 380 pricing scenarios, all seed invoices, reports, dunning, shipping and tax matrices and renders every web page (hash of the HTML). A behaviour preserving refactoring keeps it identical.

`python _ground_truth/verify_ground_truth.py` re-verifies the answer key against the code (it drops each dead-code entry in a temporary copy and checks snapshot and tests).

## Layout

```
brightshop/
  config.py        feature flags and constants
  clock.py         injectable fixed clock
  money.py         integer cent helpers (clean, well tested)
  models.py        dataclasses and exceptions
  store.py         in-memory store
  seed.py          deterministic demo data
  tax.py           VAT rates, exceptions, reverse charge
  shipping.py      zones, carriers, surcharges
  discounts.py     volume, bundles, loyalty, coupons, caps
  pricing.py       calculate_order_total (the scary core)
  invoicing.py     invoices, credit notes, payment terms, dunning
  returns.py       return policy and restocking fees
  inventory.py     stock, reorder suggestions
  customers.py     tiers, B2B status, points, credit limit
  reporting.py     KPIs, sales reports, exporters
  notifications.py customer e-mail texts
  legacy_utils.py  grab bag of old helpers
  experiments.py, fax_gateway.py   old modules
  web/             Flask app, templates, static assets (IBM Plex fonts bundled)
tests/             pytest suite
docs/              accounting export notes
_ground_truth/     answer key and snapshot (do not feed to the tool under test)
DESIGN_NOTES.md    the visual language and where it comes from
```

## License

MIT, see `LICENSE`. The bundled IBM Plex fonts are under the SIL Open Font License 1.1.
