import uuid
from sqlalchemy import Column, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class QuestionRevealRequest(Base):
    """
    Forensic contributor-identity reveal — gated the same way Auditor
    account approval already is (see app/api/auditor_governance.py):
    no single party may unilaterally learn who wrote a given question.

    An Admin opens a request against one question_id with a reason.
    QUESTION_REVEAL_APPROVAL_THRESHOLD distinct ACTIVE Auditors must
    vote before the requesting Admin can view the contributor's
    identity for that ONE question — never bulk, never the encrypted
    question content itself. Admin has no path to approve their own
    request, for the same reason Admin cannot approve Auditor accounts:
    the party whose contributors are being investigated should never
    control whether that investigation proceeds.
    """
    __tablename__ = "question_reveal_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    requested_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Null until QUESTION_REVEAL_APPROVAL_THRESHOLD auditors have voted.
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Tracked separately from approval — WHO actually opened the reveal
    # and WHEN. Approval and viewing are deliberately different moments
    # in the ledger, since in a real investigation the identity may be
    # communicated to someone outside this system entirely after this
    # point (e.g. verbally to an investigator) — this row only proves
    # the system-side view happened, not what was done with it after.
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    viewed_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)