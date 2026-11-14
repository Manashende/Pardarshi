import uuid
from sqlalchemy import Column, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class DeliveredPaper(Base):
    """
    Created ONCE, at the moment a CBT-mode unlock succeeds — see
    delivery_service.deliver_to_candidates(). questions_json holds only
    question_id, question_type, question_text, and options for each
    question; correct_option_indices is stripped before this row is ever
    written. This is the ONE place in the whole system where
    answer-redacted (but otherwise real) paper content is deliberately
    persisted — everywhere else, plaintext exists only transiently in
    memory during reconstruction. Scoped for student access via
    CandidateAssignment + VariantAssignment, and only during the exam
    window (exam_start_epoch to exam_start_epoch + exam_duration_minutes).
    """
    __tablename__ = "delivered_papers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("paper_variants.id"), nullable=False, unique=True)
    questions_json = Column(JSON, nullable=False)
    delivered_at = Column(DateTime(timezone=True), server_default=func.now())