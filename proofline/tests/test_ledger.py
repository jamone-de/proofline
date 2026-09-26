"""Tests for proofline.ledger - hash-chain integrity and tamper detection.

MIT License.
"""
from __future__ import annotations

import json
from pathlib import Path

# Point the ledger at a temporary file so tests are isolated.
import proofline.ledger as ledger_mod


def _make_ledger(tmp_path: Path) -> Path:
    """Return a fresh ledger path inside *tmp_path*."""
    p = tmp_path / "test_audit.jsonl"
    return p


# ---------------------------------------------------------------------------
# Helper: write a valid 3-entry chain to a temp file
# ---------------------------------------------------------------------------

def _build_chain(ledger_path: Path) -> list[dict]:
    """Write 3 events and return the list of written records."""
    original = ledger_mod.LEDGER_PATH
    ledger_mod.LEDGER_PATH = ledger_path
    try:
        r1 = ledger_mod.append("test", "event_1", {"x": 1})
        r2 = ledger_mod.append("test", "event_2", {"x": 2})
        r3 = ledger_mod.append("test", "event_3", {"x": 3})
    finally:
        ledger_mod.LEDGER_PATH = original
    return [r1, r2, r3]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVerifyChain:
    def test_empty_file_is_ok(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.jsonl"
        p.write_text("")
        ok, idx = ledger_mod.verify_chain(p)
        assert ok is True
        assert idx is None

    def test_missing_file_is_ok(self, tmp_path: Path) -> None:
        ok, idx = ledger_mod.verify_chain(tmp_path / "nonexistent.jsonl")
        assert ok is True
        assert idx is None

    def test_intact_chain(self, tmp_path: Path) -> None:
        lp = _make_ledger(tmp_path)
        _build_chain(lp)
        ok, idx = ledger_mod.verify_chain(lp)
        assert ok is True
        assert idx is None

    def test_tampered_middle_entry(self, tmp_path: Path) -> None:
        """Mutating the 'details' of record 1 (0-based) must break the chain."""
        lp = _make_ledger(tmp_path)
        _build_chain(lp)

        lines = lp.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[1])
        record["details"]["x"] = 999  # tamper!
        lines[1] = json.dumps(record)
        lp.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ok, idx = ledger_mod.verify_chain(lp)
        assert ok is False
        assert idx == 1

    def test_tampered_first_entry(self, tmp_path: Path) -> None:
        """Mutating record 0 breaks at index 0."""
        lp = _make_ledger(tmp_path)
        _build_chain(lp)

        lines = lp.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[0])
        record["actor"] = "HACKER"
        lines[0] = json.dumps(record)
        lp.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ok, idx = ledger_mod.verify_chain(lp)
        assert ok is False
        assert idx == 0

    def test_tampered_last_entry(self, tmp_path: Path) -> None:
        """Mutating the last record breaks at that index."""
        lp = _make_ledger(tmp_path)
        _build_chain(lp)

        lines = lp.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[-1])
        record["action"] = "INJECTED"
        lines[-1] = json.dumps(record)
        lp.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ok, idx = ledger_mod.verify_chain(lp)
        assert ok is False
        assert idx == 2

    def test_appended_without_correct_prev_hash(self, tmp_path: Path) -> None:
        """Appending a record with a fake prev_hash must be caught."""
        lp = _make_ledger(tmp_path)
        _build_chain(lp)

        fake_record = {
            "timestamp": "2099-01-01T00:00:00+00:00",
            "actor": "attacker",
            "action": "inject",
            "details": {},
            "prev_hash": "0" * 64,
            "hash": "a" * 64,
        }
        with lp.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(fake_record) + "\n")

        ok, idx = ledger_mod.verify_chain(lp)
        assert ok is False
        assert idx == 3
