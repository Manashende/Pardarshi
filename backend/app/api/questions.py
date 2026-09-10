import json
import time
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.question import Question, QuestionType, QuestionDifficulty
from app.services import item_bank_service

router = APIRouter(prefix="/questions", tags=["questions"])


# ---------------------------------------------------------------------------
# NOTE ON PYDANTIC VERSION: this uses the Pydantic v2 validator API
# (field_validator / model_validator). If this project is still on Pydantic
# v1, swap to `@validator` / `@root_validator` — check `pydantic.VERSION`
# or your requirements.txt before running this.
# ---------------------------------------------------------------------------


class SubmitQuestionRequest(BaseModel):
    question_type: QuestionType
    question_text: str = Field(..., min_length=1)
    options: List[str] = Field(..., min_length=2, max_length=6)
    correct_option_indices: List[int]
    topic: str = Field(..., min_length=1)
    difficulty: QuestionDifficulty
    tags: List[str] = []

    @field_validator("options")
    @classmethod
    def options_clean_and_unique(cls, v):
        cleaned = [o.strip() for o in v]
        if any(not o for o in cleaned):
            raise ValueError("Options cannot be blank.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Options must be unique.")
        return cleaned

    @field_validator("question_text")
    @classmethod
    def question_text_not_blank(cls, v):
        if not v.strip():
            raise ValueError("Question text cannot be blank.")
        return v.strip()

    @model_validator(mode="after")
    def validate_correct_indices(self):
        n = len(self.options)
        if not self.correct_option_indices:
            raise ValueError("At least one correct option must be selected.")
        if any(i < 0 or i >= n for i in self.correct_option_indices):
            raise ValueError("correct_option_indices out of range for the given options.")
        if len(set(self.correct_option_indices)) != len(self.correct_option_indices):
            raise ValueError("correct_option_indices contains duplicates.")
        if self.question_type == QuestionType.SINGLE_CORRECT and len(self.correct_option_indices) != 1:
            raise ValueError("Single-correct questions must have exactly one correct option.")
        return self


class QuestionMetadata(BaseModel):
    question_id: str
    topic: str
    difficulty: QuestionDifficulty
    question_type: QuestionType
    tags: List[str]
    submitted_at: float


class SubmitQuestionResponse(QuestionMetadata):
    pass


@router.post("", response_model=SubmitQuestionResponse)
def submit_question(
    req: SubmitQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.CONTRIBUTOR])),
):
    """
    Encrypts question_text + options + correct_option_indices together as one
    bundle — this is the part that must never be viewable again, by anyone,
    including the contributor who wrote it. topic/difficulty/question_type/
    tags are stored as separate plaintext columns purely for listing/filtering
    and future tag-aware selection; they reveal nothing about the answer.
    """
    content = {
        "question_type": req.question_type.value,
        "question_text": req.question_text,
        "options": req.options,
        "correct_option_indices": req.correct_option_indices,
    }
    q = Question(
        contributor_id=current_user.id,
        encrypted_content=item_bank_service.encrypt_question_content(json.dumps(content)),
        topic=req.topic,
        difficulty=req.difficulty,
        question_type=req.question_type,
        tags=req.tags,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return SubmitQuestionResponse(
        question_id=str(q.id),
        topic=q.topic,
        difficulty=q.difficulty,
        question_type=q.question_type,
        tags=q.tags,
        submitted_at=q.submitted_at.timestamp() if q.submitted_at else time.time(),
    )


@router.get("/mine", response_model=List[QuestionMetadata])
def list_my_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.CONTRIBUTOR])),
):
    """
    Metadata ONLY: question_id, topic, difficulty, question_type, tags,
    submitted_at. Never touches or returns encrypted_content. This is
    deliberately not an edit surface — once a question shows up here it is
    permanently locked, matching the no-human-view guarantee. Editing only
    happens client-side, before a question is ever submitted.
    """
    questions = (
        db.query(Question)
        .filter(Question.contributor_id == current_user.id)
        .order_by(Question.submitted_at.desc())
        .all()
    )
    return [
        QuestionMetadata(
            question_id=str(q.id),
            topic=q.topic,
            difficulty=q.difficulty,
            question_type=q.question_type,
            tags=q.tags,
            submitted_at=q.submitted_at.timestamp() if q.submitted_at else 0,
        )
        for q in questions
    ]