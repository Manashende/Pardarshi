import uuid
from sqlalchemy import Column, JSON, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class CandidateApplication(Base):
    """
    Modeled on how JEE Main / MHT-CET actually work: a student submits
    ranked centre preferences themselves (self-service, no admin
    involved at this stage) — this is the INPUT to
    candidate_allocation_service.allocate_candidates(), which produces
    CandidateAssignment rows as its OUTPUT. Keeping these as two
    separate models (rather than one) mirrors the real distinction
    between "what the candidate asked for" and "what they were actually
    given" — the same distinction a real system's audit trail would need.

    declared_latitude/longitude are optional and captured opportunistically
    (reusing the same geolocation utility already used elsewhere in the
    app) — they power the nearest-centre-with-capacity fallback when none
    of a candidate's preferred centres have room, which is a real
    improvement over how NTA/CET's opaque fallback reassignment works.
    """
    __tablename__ = "candidate_applications"
    __table_args__ = (
        UniqueConstraint("user_id", "exam_event_id", name="uq_candidate_application"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    exam_event_id = Column(UUID(as_uuid=True), ForeignKey("exam_events.id"), nullable=False)
    # Ordered list of centre id strings, most-preferred first.
    preferred_centre_ids = Column(JSON, nullable=False, default=list)
    declared_latitude = Column(Float, nullable=True)
    declared_longitude = Column(Float, nullable=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())