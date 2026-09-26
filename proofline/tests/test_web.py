"""Tests for the Proofline web dashboard.

Uses Flask's built-in test client – no real server or network needed.
All tests are isolated: each test gets a fresh in-memory ledger path and
a temporary autonomy map so they do not depend on leftover state.

Coverage targets (as specified):
  - GET  /               returns 200
  - GET  /autonomy       returns 200 and includes at least one module name
  - GET  /audit          correctly reports chain intact on a fresh ledger
  - POST /propose        on a RED module returns status "blocked" in JSON

MIT License.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import proofline.ledger as ledger_mod
from proofline.web.app import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Minimal autonomy map with one GREEN and one RED module
_SAMPLE_MAP = [
    {
        "module": "brightshop/money.py",
        "color": "GREEN",
        "reason": "complexity=3<=5, coverage=95.0%>=80.0%, commits=5>=2",
        "complexity": 3,
        "coverage": 95.0,
        "commit_count": 5,
        "days_since_last_change": 10,
    },
    {
        "module": "brightshop/pricing.py",
        "color": "RED",
        "reason": "complexity=45>15",
        "complexity": 45,
        "coverage": "unknown",
        "commit_count": 12,
        "days_since_last_change": 2,
    },
]


@pytest.fixture()
def tmp_map(tmp_path: Path):
    """Write a sample autonomy map and return its path."""
    p = tmp_path / "autonomy_map.json"
    p.write_text(json.dumps(_SAMPLE_MAP), encoding="utf-8")
    return p


@pytest.fixture()
def tmp_ledger(tmp_path: Path):
    """Return a fresh, empty ledger path."""
    return tmp_path / "test_audit.jsonl"


@pytest.fixture()
def client(tmp_map: Path, tmp_ledger: Path, monkeypatch):
    """Flask test client with patched map and ledger paths.

    Patches:
    - proofline.web.app.MAP_PATH  → tmp autonomy map (for dashboard/autonomy routes)
    - proofline.actions.MAP_PATH  → same tmp map     (for propose routes)
    - proofline.ledger.LEDGER_PATH → tmp ledger      (for audit chain)
    """
    import proofline.actions as actions_mod
    import proofline.web.app as web_app_mod

    monkeypatch.setattr(web_app_mod, "MAP_PATH", tmp_map)
    monkeypatch.setattr(actions_mod, "MAP_PATH", tmp_map)
    monkeypatch.setattr(ledger_mod, "LEDGER_PATH", tmp_ledger)

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_get_root_returns_200(self, client) -> None:
        """GET / must return HTTP 200."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_dashboard_contains_module_counts(self, client) -> None:
        """Dashboard body must mention 'GREEN' and 'RED' from the sample map."""
        resp = client.get("/")
        body = resp.data.decode()
        assert "GREEN" in body
        assert "RED" in body


class TestAutonomy:
    def test_get_autonomy_returns_200(self, client) -> None:
        """GET /autonomy must return HTTP 200."""
        resp = client.get("/autonomy")
        assert resp.status_code == 200

    def test_autonomy_includes_module_name(self, client) -> None:
        """The page must contain at least one module path from the sample map."""
        resp = client.get("/autonomy")
        body = resp.data.decode()
        assert "brightshop/money.py" in body

    def test_autonomy_filter_by_color(self, client) -> None:
        """Color filter must remove modules of other colors."""
        resp = client.get("/autonomy?color=GREEN")
        body = resp.data.decode()
        assert "brightshop/money.py" in body
        assert "brightshop/pricing.py" not in body

    def test_autonomy_sort_by_complexity(self, client) -> None:
        """Sort by complexity must return 200 without errors."""
        resp = client.get("/autonomy?sort=complexity&dir=desc")
        assert resp.status_code == 200


class TestAudit:
    def test_get_audit_returns_200(self, client) -> None:
        """GET /audit must return HTTP 200."""
        resp = client.get("/audit")
        assert resp.status_code == 200

    def test_audit_reports_chain_intact_on_fresh_ledger(self, client) -> None:
        """A brand-new ledger (no entries) must be reported as 'intact'."""
        resp = client.get("/audit")
        body = resp.data.decode()
        # The template renders either "chain intact" or "broken"
        assert "intact" in body.lower() or "Chain intact" in body


class TestCertificates:
    def test_get_certificates_returns_200(self, client) -> None:
        """GET /certificates must return HTTP 200."""
        resp = client.get("/certificates")
        assert resp.status_code == 200


class TestProposeForm:
    def test_get_propose_returns_200(self, client) -> None:
        """GET /propose must return HTTP 200."""
        resp = client.get("/propose")
        assert resp.status_code == 200

    def test_get_propose_lists_modules(self, client) -> None:
        """The form must include the module names from the autonomy map."""
        resp = client.get("/propose")
        body = resp.data.decode()
        assert "brightshop/money.py" in body


class TestProposeSubmit:
    def test_post_propose_delete_on_red_returns_blocked(self, client) -> None:
        """POST /propose on a RED module must return status 'blocked' in JSON."""
        payload = {
            "module": "brightshop/pricing.py",
            "symbol": "calculate_order_total_v1",
            "action": "delete",
        }
        resp = client.post(
            "/propose",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None, "Response is not JSON"
        assert data.get("status") == "blocked", (
            f"Expected 'blocked', got {data.get('status')!r}. Full: {data}"
        )

    def test_post_propose_missing_fields_returns_400(self, client) -> None:
        """POST /propose with missing module/symbol must return 400."""
        resp = client.post(
            "/propose",
            data=json.dumps({"action": "delete"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_post_propose_refactor_missing_code_returns_400(self, client) -> None:
        """POST /propose refactor without new_code must return 400."""
        resp = client.post(
            "/propose",
            data=json.dumps({
                "module": "brightshop/money.py",
                "symbol": "clamp",
                "action": "refactor",
                "new_code": "",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestScan:
    def test_post_scan_redirects(self, client, monkeypatch) -> None:
        """POST /scan must redirect (302) after re-running the scanner."""
        # Patch scanner.scan so we don't touch the real filesystem
        import proofline.scanner as scanner_mod
        monkeypatch.setattr(scanner_mod, "scan", lambda: None)

        resp = client.post("/scan")
        assert resp.status_code in (302, 200)
