import enum
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class QuestionType(str, enum.Enum):
    SINGLE_CORRECT = "single_correct"
    MULTIPLE_CORRECT = "multiple_correct"


class QuestionDifficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contributor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # The actual question text, options, and correct answer(s) live ONLY inside
    # encrypted_content (see item_bank_service.encrypt_question_content). Never
    # add a plaintext column for any of that.
    encrypted_content = Column(Text, nullable=False)

    # Deliberately PLAINTEXT metadata — safe to store outside the encrypted
    # bundle because none of it reveals the question or answer. This is what
    # lets a contributor list/filter their own submissions without ever
    # decrypting anything, and is also what select_questions_for_variants()
    # will eventually use for tag-aware selection (currently uniform-random —
    # see Known Gap #3 in the handoff doc).
    topic = Column(String, nullable=False, server_default="general")
    difficulty = Column(
        SAEnum(QuestionDifficulty, name="question_difficulty"),
        nullable=False,
        # NOTE: SQLAlchemy's Enum(PythonEnum) stores the member NAME
        # (e.g. "MEDIUM"), not its .value ("medium") — server_default must
        # match the uppercase name to agree with the Alembic migration.
        server_default=QuestionDifficulty.MEDIUM.name,
    )
    question_type = Column(
        SAEnum(QuestionType, name="question_type"),
        nullable=False,
        server_default=QuestionType.SINGLE_CORRECT.name,
    )
    tags = Column(JSON, nullable=False, default=list)

    submitted_at = Column(DateTime(timezone=True), server_default=func.now())