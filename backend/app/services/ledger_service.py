"""
Module 8 — hash-chained audit ledger, backed by the ledger_entries table.
Two operations only: append() and verify_chain(). Nothing else ever
touches this table from the application layer.
"""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry, LedgerEventType

GENESIS_HASH = "0" * 64


def _compute_hash(index: int, timestamp: float, event_type: str,
                   actor_id: Optional[str], exam_event_id: Optional[str],
                   details: dict, prev_hash: str) -> str:
    payload = {
        "index": index,
        "timestamp": timestamp,
        "event_type": event_type,
        "actor_id": actor_id,
        "exam_event_id": exam_event_id,
        "details": details,
        "prev_hash": prev_hash,
    }
    serialized = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(serialized).hexdigest()


def append(
    db: Session,
    event_type: LedgerEventType,
    details: dict,
    actor_id: Optional[uuid.UUID] = None,
    exam_event_id: Optional[uuid.UUID] = None,
) -> LedgerEntry:
    """Append one entry. Caller is responsible for db.commit()."""
    last_entry = (
        db.query(LedgerEntry)
        .order_by(LedgerEntry.index.desc())
        .with_for_update()
        .first()
    )
    next_index = (last_entry.index + 1) if last_entry else 0
    prev_hash = last_entry.entry_hash if last_entry else GENESIS_HASH

    # Round through datetime FIRST, then hash the rounded value — DateTime
    # columns only keep microsecond precision, but time.time() has finer
    # precision. Hashing the already-rounded value guarantees append and
    # verify always agree.
    timestamp_dt = datetime.fromtimestamp(time.time(), tz=timezone.utc)
    timestamp = timestamp_dt.timestamp()

    entry_hash = _compute_hash(
        index=next_index,
        timestamp=timestamp,
        event_type=event_type.value,
        actor_id=str(actor_id) if actor_id else None,
        exam_event_id=str(exam_event_id) if exam_event_id else None,
        details=details,
        prev_hash=prev_hash,
    )

    entry = LedgerEntry(
        index=next_index,
        event_type=event_type,
        actor_id=actor_id,
        exam_event_id=exam_event_id,
        details_json=details,
        timestamp=timestamp_dt,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session) -> dict:
    """Walk every entry, recompute hashes, confirm the chain is unbroken."""
    entries = db.query(LedgerEntry).order_by(LedgerEntry.index.asc()).all()

    expected_prev = GENESIS_HASH
    for entry in entries:
        recomputed = _compute_hash(
            index=entry.index,
            timestamp=entry.timestamp.timestamp(),
            event_type=entry.event_type.value if hasattr(entry.event_type, "value") else entry.event_type,
            actor_id=str(entry.actor_id) if entry.actor_id else None,
            exam_event_id=str(entry.exam_event_id) if entry.exam_event_id else None,
            details=entry.details_json,
            prev_hash=entry.prev_hash,
        )
        if entry.prev_hash != expected_prev or recomputed != entry.entry_hash:
            return {"chain_intact": False, "entries_checked": len(entries), "first_broken_index": entry.index}
        expected_prev = entry.entry_hash

    return {"chain_intact": True, "entries_checked": len(entries), "first_broken_index": None}