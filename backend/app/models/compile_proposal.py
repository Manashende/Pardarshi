import uuid
from sqlalchemy import Column, String, Integer, JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class CompileProposal(Base):
    """
    Closes a real known gap: previously, a single Admin could
    unilaterally pick the entire custodian list and immediately compile
    — no check that another human agreed those people were actually
    independent, appropriate custodians. Same no-single-party-trust
    principle applied elsewhere in this project (Shamir reconstruction,
    Auditor account governance) now applies here too: an Admin PROPOSES
    a compile (the custodian list + selection parameters), and a
    DIFFERENT Admin must CONFIRM it before the actual compile executes.

    One active proposal per exam event at a time — proposing again
    replaces any prior undecided proposal and requires fresh
    confirmation from a (still different) admin.

    The assignment_secret is deliberately NOT stored here — it was only
    ever held by whoever created the exam event, and is supplied again
    at confirm-time, exactly as before this change.
    """
    __tablename__ = "compile_proposals"
    __table_args__ = (
        UniqueConstraint("exam_event_id", name="uq_compile_proposal_per_event"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_event_id = Column(UUID(as_uuid=True), ForeignKey("exam_events.id"), nullable=False)
    proposed_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    questions_per_variant = Column(Integer, nullable=False)
    custodian_user_ids = Column(JSON, nullable=False)
    custodian_types = Column(JSON, nullable=False)
    exam_date = Column(String, nullable=False)
    difficulty_distribution = Column(JSON, nullable=True)
    subject_distribution = Column(JSON, nullable=True)
    proposed_at = Column(DateTime(timezone=True), server_default=func.now())