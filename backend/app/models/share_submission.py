import uuid
import enum
from sqlalchemy import Column, Float, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class SubmissionType(str, enum.Enum):
    STANDARD = "STANDARD"
    OVERRIDE = "OVERRIDE"


class ShareSubmission(Base):
    """
    Module 3/4 — one record per share submission attempt. ntp_verified_time
    is the cross-checked time from Algorithm C at submission, kept for
    audit even if this submission isn't part of the eventual threshold.
    """
    __tablename__ = "share_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("paper_variants.id"), nullable=False)
    custodian_id = Column(UUID(as_uuid=True), ForeignKey("custodians.id"), nullable=False)
    submission_type = Column(Enum(SubmissionType), nullable=False, default=SubmissionType.STANDARD)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    ntp_verified_time = Column(Float, nullable=False)