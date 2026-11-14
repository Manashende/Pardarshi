import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class Topic(Base):
    """
    Admin-managed, per-deployment topic taxonomy — the real fix for
    inconsistent topic spelling in the item bank (see
    item_bank_service._normalize_topic's docstring). Deliberately just
    (id, name): Pardarshi is meant to serve ANY exam board, so the set
    of valid topics is data an Admin configures per deployment, never
    something hardcoded in application code.

    No delete/rename support yet, on purpose — either would risk
    silently orphaning existing Question.topic values that already
    reference a name. That's real, separate future work, not an
    oversight.
    """
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())