import uuid
from sqlalchemy import Column, JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class CandidateSubmission(Base):
    """
    One row per (candidate, variant) — a candidate can only submit once,
    enforced by the unique constraint below, mirroring the same
    submit-and-lock pattern used for item bank questions. answers_json
    maps question_id -> selected option index/indices. No grading logic
    anywhere — this table exists purely to make submission a real,
    audited event (see LedgerEventType.EXAM_SUBMITTED) rather than
    something that evaporates in browser state on refresh. Grading is a
    deliberate scope boundary, not an oversight — it's orthogonal to
    this project's actual thesis (leak prevention via threshold crypto),
    and should be named as such in the report's limitations section.
    """
    __tablename__ = "candidate_submissions"
    __table_args__ = (
        UniqueConstraint("candidate_user_id", "variant_id", name="uq_candidate_submission_once"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("paper_variants.id"), nullable=False)
    answers_json = Column(JSON, nullable=False, default=dict)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())