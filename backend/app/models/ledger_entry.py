import uuid
import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class LedgerEventType(str, enum.Enum):
    QUESTION_SUBMITTED = "QUESTION_SUBMITTED"
    VARIANTS_COMPILED = "VARIANTS_COMPILED"
    SHARE_SUBMITTED = "SHARE_SUBMITTED"
    UNLOCK_DENIED_THRESHOLD = "UNLOCK_DENIED_THRESHOLD"
    UNLOCK_DENIED_TIME = "UNLOCK_DENIED_TIME"
    VARIANT_DECRYPTED = "VARIANT_DECRYPTED"
    PRINT_JOB_COMPLETED = "PRINT_JOB_COMPLETED"
    ACCESS_DENIED = "ACCESS_DENIED"
    OVERRIDE_REQUESTED = "OVERRIDE_REQUESTED"
    OVERRIDE_APPROVED = "OVERRIDE_APPROVED"


class LedgerEntry(Base):
    """
    Module 8 — append-only, hash-chained audit log. `index` is this
    entry's position. `prev_hash` is the entry_hash of the entry right
    before it (64 zero-chars for the genesis entry). `entry_hash` is
    computed by ledger_service.append() before insert — never by the DB.

    timestamp is set explicitly by the service layer (not a DB-side
    default) because the hash must be computed over the EXACT value
    that ends up stored — a DB-generated default would differ from
    whatever the app hashed, breaking verification even with zero
    tampering.

    The app must NEVER allow UPDATE/DELETE on this table — only INSERT.
    Enforce with DB-level permissions in production, not just app-layer
    discipline.
    """
    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    index = Column(Integer, unique=True, nullable=False)
    event_type = Column(Enum(LedgerEventType), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    exam_event_id = Column(UUID(as_uuid=True), ForeignKey("exam_events.id"), nullable=True)
    details_json = Column(JSON, nullable=False, default=dict)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    prev_hash = Column(String, nullable=False)
    entry_hash = Column(String, nullable=False)