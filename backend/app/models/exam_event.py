import uuid
import enum
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class ExamEventStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    COMPILED = "COMPILED"
    LIVE = "LIVE"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class DeliveryMode(str, enum.Enum):
    # CBT is the core mode: strict exact-exam-start time lock, no early
    # release under any circumstance — a digital paper is too easy to
    # silently copy once decrypted, so there's no substitute trust
    # mechanism offered the way there is for PRINT.
    CBT = "CBT"
    # PRINT is the optional/offline mode: reconstruction may begin up to
    # print_window_hours before exam start, but only once
    # required_officials_count named, identified on-site officials have
    # confirmed physical presence (see OfficialPresenceConfirmation) —
    # accountability substitutes for exact-second timing precision here.
    PRINT = "PRINT"


class ExamEvent(Base):
    __tablename__ = "exam_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_name = Column(String, nullable=False)
    exam_start_epoch = Column(Float, nullable=False)
    override_window_end_epoch = Column(Float, nullable=False)
    num_variants = Column(Integer, nullable=False)
    questions_per_variant = Column(Integer, nullable=False, server_default='5')
    # Which centres this exam actually runs at — confirm_compile assigns
    # variants only among THESE centres, not every registered centre.
    centre_ids = Column(JSON, nullable=False, default=list)
    threshold = Column(Integer, nullable=False)
    total_custodians = Column(Integer, nullable=False)
    override_threshold = Column(Integer, nullable=False)
    assignment_secret_hash = Column(String, nullable=False)
    status = Column(Enum(ExamEventStatus), nullable=False, default=ExamEventStatus.DRAFT)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    delivery_mode = Column(
        Enum(DeliveryMode), nullable=False,
        default=DeliveryMode.CBT, server_default=DeliveryMode.CBT.value,
    )
    # Only meaningful when delivery_mode == PRINT.
    print_window_hours = Column(Integer, nullable=False, default=2, server_default='2')
    # Only meaningful when delivery_mode == PRINT.
    required_officials_count = Column(Integer, nullable=False, default=2, server_default='2')
    # How long a CBT candidate has once the exam paper is delivered to
    # their terminal. exam_start_epoch/override_window_end_epoch are
    # crypto deadlines, not "when does the exam end" — nothing else on
    # this model represents actual exam duration.
    exam_duration_minutes = Column(Integer, nullable=False, default=180, server_default='180')