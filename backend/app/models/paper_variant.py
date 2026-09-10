import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class PaperVariant(Base):
    __tablename__ = "paper_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_event_id = Column(UUID(as_uuid=True), ForeignKey("exam_events.id"), nullable=False)
    variant_index = Column(Integer, nullable=False)
    ciphertext = Column(Text, nullable=False)
    nonce = Column(String, nullable=False)
    question_ids = Column(JSON, nullable=False, default=list)