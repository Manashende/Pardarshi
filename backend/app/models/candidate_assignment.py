import uuid
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class CandidateAssignment(Base):
    """
    Same pattern as CentreOperatorAssignment and Custodian: a student is
    tied to one centre for one exam event, admin-assigned. This is what
    scopes which delivered paper a given student is allowed to fetch —
    a student can only ever retrieve the DeliveredPaper for the variant
    assigned (via VariantAssignment) to their own centre for this event.
    """
    __tablename__ = "candidate_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "exam_event_id", name="uq_candidate_assignment"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    exam_event_id = Column(UUID(as_uuid=True), ForeignKey("exam_events.id"), nullable=False)
    centre_id = Column(UUID(as_uuid=True), ForeignKey("exam_centres.id"), nullable=False)