import uuid
from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class QuestionRevealVote(Base):
    __tablename__ = "question_reveal_votes"
    __table_args__ = (
        # One vote per auditor per request — mirrors the existing_vote
        # check already done in app-code for AuditorApprovalVote, added
        # here as a real DB constraint too, not just an app-level check.
        UniqueConstraint("reveal_request_id", "voting_auditor_id", name="uq_reveal_vote_per_auditor"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reveal_request_id = Column(UUID(as_uuid=True), ForeignKey("question_reveal_requests.id"), nullable=False)
    voting_auditor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    voted_at = Column(DateTime(timezone=True), server_default=func.now())