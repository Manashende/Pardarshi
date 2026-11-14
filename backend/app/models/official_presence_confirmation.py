import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class OfficialPresenceConfirmation(Base):
    """
    PRINT-mode accountability mechanism: since printing can now begin up
    to print_window_hours before exam start (see ExamEvent), the
    exact-second time lock CBT relies on no longer applies there. In its
    place, a fixed number of named, identified on-site officials (any
    user with an existing CentreOperatorAssignment for that centre) must
    each confirm physical presence — device + location checked the same
    way unlock's own access check works — before attempt_unlock will
    allow reconstruction for a PRINT-mode exam event. This is what makes
    "who's accountable if this leaks" a real, queryable fact in the
    ledger rather than a procedural assumption.
    """
    __tablename__ = "official_presence_confirmations"
    __table_args__ = (
        UniqueConstraint("exam_event_id", "centre_id", "official_user_id",
                          name="uq_official_presence_once"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_event_id = Column(UUID(as_uuid=True), ForeignKey("exam_events.id"), nullable=False)
    centre_id = Column(UUID(as_uuid=True), ForeignKey("exam_centres.id"), nullable=False)
    official_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), server_default=func.now())
    declared_latitude = Column(Float, nullable=False)
    declared_longitude = Column(Float, nullable=False)
    device_fingerprint = Column(String, nullable=False)