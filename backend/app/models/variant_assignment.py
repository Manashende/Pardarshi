import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class VariantAssignment(Base):
    """
    Module 6 / Algorithm E — which centre got which paper variant.
    assignment_hash = HMAC(assignment_secret, centre_id || exam_date):
    reproducible for audit, not predictable without the secret.
    """
    __tablename__ = "variant_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_event_id = Column(UUID(as_uuid=True), ForeignKey("exam_events.id"), nullable=False)
    centre_id = Column(UUID(as_uuid=True), ForeignKey("exam_centres.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("paper_variants.id"), nullable=False)
    assignment_hash = Column(String, nullable=False)