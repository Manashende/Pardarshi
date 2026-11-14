import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class AccessAttempt(Base):
    """
    Module 5 / Algorithm D — logged for EVERY sensitive action, pass or
    fail. overall_passed is only True if all four checks pass. Feeds the
    "flagged access attempts" panel on the admin dashboard (Module 9).
    """
    __tablename__ = "access_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)

    role_check_passed = Column(Boolean, nullable=False)
    device_check_passed = Column(Boolean, nullable=False)
    location_check_passed = Column(Boolean, nullable=False)
    time_window_check_passed = Column(Boolean, nullable=False)
    overall_passed = Column(Boolean, nullable=False)

    declared_latitude = Column(Float, nullable=True)
    declared_longitude = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())