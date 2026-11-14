import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        # Prevents the exact duplicate-row bug seen in testing: without a
        # DB-level constraint, a check-then-insert race (e.g. two rapid
        # requests for the same user+fingerprint) can create two rows for
        # what should be one device. This makes that structurally
        # impossible rather than just less likely.
        UniqueConstraint("user_id", "fingerprint", name="uq_device_user_fingerprint"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    fingerprint = Column(String, nullable=False)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True, nullable=False)