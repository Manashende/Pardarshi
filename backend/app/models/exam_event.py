import uuid
import enum
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class ExamEventStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    COMPILED = "COMPILED"
    LIVE = "LIVE"
    CLOSED = "CLOSED"


class ExamEvent(Base):
    __tablename__ = "exam_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_name = Column(String, nullable=False)
    exam_start_epoch = Column(Float, nullable=False)
    override_window_end_epoch = Column(Float, nullable=False)
    num_variants = Column(Integer, nullable=False)
    threshold = Column(Integer, nullable=False)
    total_custodians = Column(Integer, nullable=False)
    override_threshold = Column(Integer, nullable=False)
    assignment_secret_hash = Column(String, nullable=False)
    status = Column(Enum(ExamEventStatus), nullable=False, default=ExamEventStatus.DRAFT)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)