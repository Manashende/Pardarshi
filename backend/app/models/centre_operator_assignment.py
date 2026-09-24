import uuid
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class CentreOperatorAssignment(Base):
    """
    No equivalent of this existed before Phase B. Custodian already ties a
    user to an exam_event via the Custodian table; ExamCentre had NOTHING
    tying it to a CENTRE_OPERATOR user. Without this, the unlock endpoint
    had no way to verify a centre operator was actually assigned to the
    centre they claimed in a request — it just trusted the request body.
    This table is what unlock's access check now verifies against.
    """
    __tablename__ = "centre_operator_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "centre_id", name="uq_centre_operator_assignment"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    centre_id = Column(UUID(as_uuid=True), ForeignKey("exam_centres.id"), nullable=False)