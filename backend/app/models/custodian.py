import uuid
import enum
from sqlalchemy import Column, String, Integer, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class CustodianType(str, enum.Enum):
    EXAM_BOARD_REP = "EXAM_BOARD_REP"
    INDEPENDENT_REGULATOR = "INDEPENDENT_REGULATOR"
    MAGISTRATE_OBSERVER = "MAGISTRATE_OBSERVER"
    STATE_EDU_OFFICER = "STATE_EDU_OFFICER"
    JUDICIARY_AUDITOR = "JUDICIARY_AUDITOR"


class Custodian(Base):
    """
    Module 3 — one custodian's SSS share for one exam event. share_y is
    stored encrypted at rest — the plaintext y-value should never be
    readable directly from the database, even by an admin with DB
    access. Only share_x (the public x-coordinate) is stored in the
    clear, since x alone reveals nothing about the secret.
    """
    __tablename__ = "custodians"
    __table_args__ = (
        # Two custodians on the same exam event must never share an
        # x-coordinate — that would silently break Shamir reconstruction.
        UniqueConstraint("exam_event_id", "share_x", name="uq_custodian_event_sharex"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    exam_event_id = Column(UUID(as_uuid=True), ForeignKey("exam_events.id"), nullable=False)
    custodian_type = Column(Enum(CustodianType), nullable=False)
    share_x = Column(Integer, nullable=False)
