"""Hash-chained audit ledger for Proofline.

Every event is appended as a JSON line to *proofline_audit.jsonl*.
Each record contains a SHA-256 digest over itself plus the previous
hash, forming an append-only chain.  ``verify_chain()`` walks the
file and detects any tampering.

MIT License.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_PATH = Path("proofline_audit.jsonl")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _canonical(obj: dict) -> bytes:
    """Return deterministic UTF-8 JSON bytes (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(data: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def _compute_hash(prev_hash: str, record_fields: dict) -> str:
    """Compute the chain hash for a record.

    The digest covers *prev_hash* concatenated with the canonical JSON of
    every field in *record_fields* (everything except the ``hash`` key itself).
    """
    payload = prev_hash.encode() + _canonical(record_fields)
    return _sha256(payload)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def append(actor: str, action: str, details: Any = None) -> dict:
    """Append one event to the ledger and return the written record.

    Parameters
    ----------
    actor:
        Who triggered the event (e.g. ``"proofline/actions"``).
    action:
        Short verb describing what happened (e.g. ``"propose_delete"``).
    details:
        Arbitrary JSON-serialisable payload.  ``None`` is stored as ``{}``.
    """
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)

    prev_hash = _tail_hash()

    fields: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "details": details if details is not None else {},
        "prev_hash": prev_hash,
    }
    record_hash = _compute_hash(prev_hash, fields)
    record = {**fields, "hash": record_hash}

    with LEDGER_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def verify_chain(path: Path | None = None) -> tuple[bool, int | None]:
    """Walk the ledger and verify every hash link.

    Returns
    -------
    (True, None)
        When the chain is intact.
    (False, first_broken_index)
        When a record's stored hash does not match the recomputed one.
        *first_broken_index* is 0-based.
    """
    target = path or LEDGER_PATH
    if not target.exists():
        return True, None

    prev_hash = "0" * 64  # genesis sentinel
    with target.open(encoding="utf-8") as fh:
        for idx, raw in enumerate(fh):
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                return False, idx

            stored_hash = record.get("hash", "")
            fields = {k: v for k, v in record.items() if k != "hash"}
            expected_prev = fields.get("prev_hash", "")

            if expected_prev != prev_hash:
                return False, idx

            recomputed = _compute_hash(prev_hash, fields)
            if recomputed != stored_hash:
                return False, idx

            prev_hash = stored_hash

    return True, None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _tail_hash() -> str:
    """Return the hash of the last record, or the genesis sentinel."""
    if not LEDGER_PATH.exists():
        return "0" * 64
    last = ""
    with LEDGER_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                last = stripped
    if not last:
        return "0" * 64
    try:
        return json.loads(last).get("hash", "0" * 64)
    except json.JSONDecodeError:
        return "0" * 64
