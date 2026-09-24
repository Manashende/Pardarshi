import time
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.exam_event import ExamEvent, ExamEventStatus
from app.models.exam_centre import ExamCentre
from app.models.paper_variant import PaperVariant
from app.models.custodian import Custodian, CustodianType
from app.models.variant_assignment import VariantAssignment
from app.services import compile_service, variant_assignment, ledger_service, item_bank_service
from app.models.ledger_entry import LedgerEventType

router = APIRouter(prefix="/exam-events", tags=["exam-events"])


class CreateExamEventRequest(BaseModel):
    exam_name: str
    exam_start_epoch: float
    override_window_end_epoch: float
    num_variants: int
    threshold: int
    total_custodians: int
    override_threshold: int
    centre_ids: List[str]


@router.post("")
def create_exam_event(
    req: CreateExamEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    secret = variant_assignment.generate_assignment_secret()
    secret_hash = variant_assignment.hash_secret_for_storage(secret)

    event = ExamEvent(
        exam_name=req.exam_name,
        exam_start_epoch=req.exam_start_epoch,
        override_window_end_epoch=req.override_window_end_epoch,
        num_variants=req.num_variants,
        threshold=req.threshold,
        total_custodians=req.total_custodians,
        override_threshold=req.override_threshold,
        assignment_secret_hash=secret_hash,
        status=ExamEventStatus.DRAFT,
        created_by=current_user.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # NOTE: the raw `secret` (not just its hash) is needed again at
    # compile time to actually compute assignments. For this pass it's
    # returned once here for the caller to hold onto and pass back into
    # /compile — a production version would want a proper secrets
    # manager rather than round-tripping it through the API response.
    return {"exam_event_id": str(event.id), "assignment_secret": secret.hex()}


class CompileRequest(BaseModel):
    questions_per_variant: int  # Module 1 — how many item-bank questions to auto-select per variant
    custodian_user_ids: List[str]
    custodian_types: List[str]
    assignment_secret: str  # hex string returned by /exam-events on creation
    exam_date: str  # e.g. "2027-01-15"

@router.get("")
def list_exam_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    events = db.query(ExamEvent).all()
    
    # Returning a list of dictionaries to ensure FastAPI serializes the SQLAlchemy models cleanly
    return [
        {
            "id": str(e.id),
            "exam_name": e.exam_name,
            "exam_start_epoch": e.exam_start_epoch,
            "override_window_end_epoch": e.override_window_end_epoch,
            "num_variants": e.num_variants,
            "threshold": e.threshold,
            "total_custodians": e.total_custodians,
            "override_threshold": e.override_threshold,
            "status": e.status.value,
        }
        for e in events
    ]

@router.post("/{exam_event_id}/compile")
def compile_exam_event(
    exam_event_id: UUID,
    req: CompileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    event = db.query(ExamEvent).filter(ExamEvent.id == exam_event_id).first()
    if event is None:
        raise HTTPException(404, "exam event not found")
    if event.status != ExamEventStatus.DRAFT:
        raise HTTPException(400, f"exam event is '{event.status.value}', can only compile from DRAFT")

    secret = bytes.fromhex(req.assignment_secret)
    custodian_types = [CustodianType(t) for t in req.custodian_types]

    # Custodian IDENTITY is created once for the whole exam event —
    # the same 5 people serve every variant, each holding one fixed
    # x-coordinate. Their per-variant y-values are generated separately
    # below, inside compile_service.compile_variant, since each variant
    # has its own independent key.
    custodians = compile_service.get_or_create_custodians(
        db, exam_event_id=event.id,
        custodian_user_ids=[UUID(u) for u in req.custodian_user_ids],
        custodian_types=custodian_types,
    )

    # Module 1 — automated, no-human-view selection + assembly from the
    # encrypted item bank. Raises InsufficientQuestionsError if the bank
    # is too small; that propagates as a 400 below rather than silently
    # producing a short/broken paper.
    try:
        selection = item_bank_service.select_questions_for_variants(
            db, num_variants=event.num_variants, questions_per_variant=req.questions_per_variant,
        )
    except item_bank_service.InsufficientQuestionsError as e:
        raise HTTPException(400, str(e))

    variants = []
    for variant_index, variant_questions in enumerate(selection):
        plaintext = item_bank_service.assemble_variant_plaintext(variant_questions)
        variant = compile_service.compile_variant(
            db, exam_event_id=event.id, variant_index=variant_index,
            plaintext=plaintext, custodians=custodians, threshold=event.threshold,
            question_ids=[q.id for q in variant_questions],
        )
        variants.append(variant)

    centres = db.query(ExamCentre).all()
    assignments = []
    for centre in centres:
        a = variant_assignment.compute_assignment(secret, str(centre.id), req.exam_date, event.num_variants)
        variant = variants[a["variant_index"]]
        assignment = VariantAssignment(
            exam_event_id=event.id, centre_id=centre.id, variant_id=variant.id,
            assignment_hash=a["assignment_hash"],
        )
        db.add(assignment)
        assignments.append(assignment)

    event.status = ExamEventStatus.COMPILED
    ledger_service.append(db, LedgerEventType.VARIANTS_COMPILED, details={
        "exam_event_id": str(event.id), "num_variants": event.num_variants,
        "num_centres_assigned": len(assignments),
    }, actor_id=current_user.id, exam_event_id=event.id)
    db.commit()

    return {
        "exam_event_id": str(event.id),
        "variants": [{"variant_id": str(v.id), "variant_index": v.variant_index} for v in variants],
        "assignments_created": len(assignments),
    }