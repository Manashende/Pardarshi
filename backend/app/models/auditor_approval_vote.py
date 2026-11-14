import uuid
from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class AuditorApprovalVote(Base):
    """
    Applies the same no-single-party-trust principle Shamir's Secret
    Sharing already applies to cryptographic access — here, to account
    governance. A pending AUDITOR-role account activates only once
    AUDITOR_APPROVAL_THRESHOLD distinct EXISTING active Auditors have
    each cast a vote here — Admin is deliberately not part of this path
    (see app/api/auditor_governance.py and the bootstrap exception noted
    there), because the person being audited must never control who
    gets to audit them.
    """
    __tablename__ = "auditor_approval_votes"
    __table_args__ = (
        UniqueConstraint("pending_user_id", "voting_auditor_id", name="uq_auditor_approval_vote"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pending_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    voting_auditor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    voted_at = Column(DateTime(timezone=True), server_default=func.now())