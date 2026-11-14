"""
Candidate (student)-facing endpoints, plus admin allocation.

Two-stage flow, modeled on JEE Main / MHT-CET: a student self-applies
with ranked centre preferences (no admin involved), then an admin
triggers ONE bulk allocation pass for the whole exam event
(candidate_allocation_service.allocate_candidates) rather than picking
students one at a time. A direct manual /assign endpoint is kept for
edge-case overrides (e.g. correcting a single mistaken allocation), but
it is NOT the primary path.

CRITICAL: /me/paper/{variant_id} returns ONLY DeliveredPaper.questions_json
— which never contains correct_option_indices (stripped by
delivery_service.redact_paper_text before this row ever existed). Never
add a field here that reaches back into the encrypted or reconstructed
content directly.
"""
import time
from typing import List, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.exam_event import ExamEvent
from app.models.exam_centre import ExamCentre
from app.models.paper_variant import PaperVariant
from app.models.variant_assignment import VariantAssignment
from app.models.candidate_application import CandidateApplication
from app.models.candidate_assignment import CandidateAssignment
from app.models.delivered_paper import DeliveredPaper
from app.models.candidate_submission import CandidateSubmission
from app.models.ledger_entry import LedgerEventType
from app.services import ledger_service, candidate_allocation_service

router = APIRouter(prefix="/candidates", tags=["candidates"])


# ---------------------------------------------------------------------------
# Student: self-apply with ranked centre preferences
# ---------------------------------------------------------------------------

class ApplyRequest(BaseModel):
    exam_event_id: str
    preferred_centre_ids: List[str]  # ordered, most-preferred first
    declared_latitude: Optional[float] = None
    declared_longitude: Optional[float] = None


class ApplicationOut(BaseModel):
    exam_event_id: str
    preferred_centre_ids: List[str]
    applied_at: float


@router.post("/apply", response_model=ApplicationOut)
def apply_for_exam(
    req: ApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT])),
):
    event = db.query(ExamEvent).filter(ExamEvent.id == UUID(req.exam_event_id)).first()
    if event is None:
        raise HTTPException(404, "exam event not found")
    if len(req.preferred_centre_ids) == 0:
        raise HTTPException(400, "at least one preferred centre is required")
    if len(set(req.preferred_centre_ids)) != len(req.preferred_centre_ids):
        raise HTTPException(400, "each preference must be a different centre")
    for cid in req.preferred_centre_ids:
        if db.query(ExamCentre).filter(ExamCentre.id == UUID(cid)).first() is None:
            raise HTTPException(400, f"centre {cid} does not exist")

    # Applications are one-shot, matching the same submit-and-lock pattern
    # used for item bank questions and custodian shares — once submitted,
    # no further edits, at all, even before allocation runs.
    existing_application = (
        db.query(CandidateApplication)
        .filter(CandidateApplication.user_id == current_user.id, CandidateApplication.exam_event_id == event.id)
        .first()
    )
    if existing_application is not None:
        raise HTTPException(400, "you have already submitted your preferences for this exam — applications cannot be edited once submitted")

    application = CandidateApplication(
        user_id=current_user.id, exam_event_id=event.id,
        preferred_centre_ids=req.preferred_centre_ids,
        declared_latitude=req.declared_latitude, declared_longitude=req.declared_longitude,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    return ApplicationOut(
        exam_event_id=str(event.id), preferred_centre_ids=application.preferred_centre_ids,
        applied_at=application.applied_at.timestamp() if application.applied_at else time.time(),
    )


class MyApplicationSummary(BaseModel):
    exam_event_id: str
    exam_name: str
    applied_at: float


@router.get("/me/applications", response_model=List[MyApplicationSummary])
def my_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT])),
):
    """
    ALL of this student's applications (not scoped to one exam event) —
    lets the frontend filter the "apply" exam picker down to only events
    not yet applied to, in a single call rather than one per event.
    """
    rows = db.query(CandidateApplication).filter(CandidateApplication.user_id == current_user.id).all()
    result = []
    for r in rows:
        event = db.query(ExamEvent).filter(ExamEvent.id == r.exam_event_id).first()
        if event is None:
            continue
        result.append(MyApplicationSummary(
            exam_event_id=str(r.exam_event_id), exam_name=event.exam_name,
            applied_at=r.applied_at.timestamp() if r.applied_at else 0,
        ))
    return result


class MyApplicationOut(BaseModel):
    exam_event_id: str
    preferred_centre_ids: List[str]
    applied_at: float
    allocated: bool
    allocated_centre_code: Optional[str] = None


@router.get("/me/application/{exam_event_id}")
def my_application(
    exam_event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT])),
):
    application = (
        db.query(CandidateApplication)
        .filter(CandidateApplication.user_id == current_user.id, CandidateApplication.exam_event_id == exam_event_id)
        .first()
    )
    if application is None:
        return None

    assignment = (
        db.query(CandidateAssignment)
        .filter(CandidateAssignment.user_id == current_user.id, CandidateAssignment.exam_event_id == exam_event_id)
        .first()
    )
    centre_code = None
    if assignment is not None:
        centre = db.query(ExamCentre).filter(ExamCentre.id == assignment.centre_id).first()
        centre_code = centre.centre_code if centre else None

    return MyApplicationOut(
        exam_event_id=str(exam_event_id), preferred_centre_ids=application.preferred_centre_ids,
        applied_at=application.applied_at.timestamp() if application.applied_at else 0,
        allocated=assignment is not None, allocated_centre_code=centre_code,
    )


# ---------------------------------------------------------------------------
# Admin: bulk allocation (primary path) + manual override (edge cases only)
# ---------------------------------------------------------------------------

class AllocationResultOut(BaseModel):
    user_id: str
    user_email: str
    centre_id: Optional[str]
    centre_code: Optional[str]
    method: str
    preference_rank: Optional[int]


@router.post("/allocate/{exam_event_id}", response_model=List[AllocationResultOut])
def run_allocation(
    exam_event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    event = db.query(ExamEvent).filter(ExamEvent.id == exam_event_id).first()
    if event is None:
        raise HTTPException(404, "exam event not found")

    outcomes = candidate_allocation_service.allocate_candidates(
        db, exam_event_id, triggered_by_admin_id=current_user.id,
    )

    result = []
    for o in outcomes:
        user = db.query(User).filter(User.id == UUID(o.user_id)).first()
        centre = db.query(ExamCentre).filter(ExamCentre.id == UUID(o.centre_id)).first() if o.centre_id else None
        result.append(AllocationResultOut(
            user_id=o.user_id, user_email=user.email if user else "unknown",
            centre_id=o.centre_id, centre_code=centre.centre_code if centre else None,
            method=o.method, preference_rank=o.preference_rank,
        ))
    return result


class AssignCandidateRequest(BaseModel):
    user_id: str
    exam_event_id: str
    centre_id: str


class CandidateAssignmentOut(BaseModel):
    id: str
    user_id: str
    user_email: str
    exam_event_id: str
    exam_name: str
    centre_id: str
    centre_code: str


@router.post("/assign", response_model=CandidateAssignmentOut)
def assign_candidate_manually(
    req: AssignCandidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """
    Manual override — NOT the primary allocation path. Use /allocate for
    bulk, preference-based allocation. This exists for edge cases: fixing
    a mistaken allocation, or handling a candidate who never applied.
    """
    user = db.query(User).filter(User.id == UUID(req.user_id)).first()
    if user is None:
        raise HTTPException(404, "user not found")
    if user.role != UserRole.STUDENT:
        raise HTTPException(400, "user does not have the STUDENT role")

    event = db.query(ExamEvent).filter(ExamEvent.id == UUID(req.exam_event_id)).first()
    if event is None:
        raise HTTPException(404, "exam event not found")

    centre = db.query(ExamCentre).filter(ExamCentre.id == UUID(req.centre_id)).first()
    if centre is None:
        raise HTTPException(404, "centre not found")

    existing = (
        db.query(CandidateAssignment)
        .filter(CandidateAssignment.user_id == user.id, CandidateAssignment.exam_event_id == event.id)
        .first()
    )
    if existing is None:
        existing = CandidateAssignment(user_id=user.id, exam_event_id=event.id, centre_id=centre.id)
        db.add(existing)
        ledger_service.append(
            db, LedgerEventType.CANDIDATE_ALLOCATED,
            details={"candidate_id": str(user.id), "centre_id": str(centre.id), "method": "manual_override"},
            actor_id=current_user.id, exam_event_id=event.id,
        )
        db.commit()
        db.refresh(existing)

    return CandidateAssignmentOut(
        id=str(existing.id), user_id=str(user.id), user_email=user.email,
        exam_event_id=str(event.id), exam_name=event.exam_name,
        centre_id=str(centre.id), centre_code=centre.centre_code,
    )


@router.get("/assignments", response_model=List[CandidateAssignmentOut])
def list_candidate_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR])),
):
    rows = db.query(CandidateAssignment).all()
    result = []
    for row in rows:
        user = db.query(User).filter(User.id == row.user_id).first()
        event = db.query(ExamEvent).filter(ExamEvent.id == row.exam_event_id).first()
        centre = db.query(ExamCentre).filter(ExamCentre.id == row.centre_id).first()
        if user is None or event is None or centre is None:
            continue
        result.append(CandidateAssignmentOut(
            id=str(row.id), user_id=str(user.id), user_email=user.email,
            exam_event_id=str(event.id), exam_name=event.exam_name,
            centre_id=str(centre.id), centre_code=centre.centre_code,
        ))
    return result


# ---------------------------------------------------------------------------
# Student: exam-day discovery, paper fetch, submission (unchanged from
# before this redesign — CandidateAssignment is populated by /allocate now
# instead of one-at-a-time admin picks, but everything downstream of it
# works exactly the same way)
# ---------------------------------------------------------------------------

class MyExamAssignment(BaseModel):
    exam_event_id: str
    exam_name: str
    exam_status: str
    centre_id: str
    centre_code: str
    centre_name: str
    variant_id: Optional[str]
    exam_start_epoch: float
    exam_duration_minutes: int
    paper_delivered: bool
    has_submitted: bool


@router.get("/me/assignments", response_model=List[MyExamAssignment])
def my_exam_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT])),
):
    rows = db.query(CandidateAssignment).filter(CandidateAssignment.user_id == current_user.id).all()
    result = []
    for row in rows:
        event = db.query(ExamEvent).filter(ExamEvent.id == row.exam_event_id).first()
        centre = db.query(ExamCentre).filter(ExamCentre.id == row.centre_id).first()
        if event is None or centre is None:
            continue

        variant_assignment = (
            db.query(VariantAssignment)
            .filter(VariantAssignment.exam_event_id == event.id, VariantAssignment.centre_id == row.centre_id)
            .first()
        )
        variant_id = variant_assignment.variant_id if variant_assignment else None

        delivered = False
        has_submitted = False
        if variant_id is not None:
            delivered = db.query(DeliveredPaper).filter(DeliveredPaper.variant_id == variant_id).first() is not None
            has_submitted = (
                db.query(CandidateSubmission)
                .filter(CandidateSubmission.candidate_user_id == current_user.id,
                        CandidateSubmission.variant_id == variant_id)
                .first()
                is not None
            )

        result.append(MyExamAssignment(
            exam_event_id=str(event.id),
            exam_name=event.exam_name,
            exam_status=event.status.value,
            centre_id=str(centre.id),
            centre_code=centre.centre_code,
            centre_name=centre.name,
            variant_id=str(variant_id) if variant_id else None,
            exam_start_epoch=event.exam_start_epoch,
            exam_duration_minutes=event.exam_duration_minutes,
            paper_delivered=delivered,
            has_submitted=has_submitted,
        ))
    return result


class DeliveredQuestion(BaseModel):
    question_id: str
    question_type: str
    question_text: str
    options: List[str]
    tags: List[str]


class DeliveredPaperOut(BaseModel):
    variant_id: str
    exam_end_epoch: float
    questions: List[DeliveredQuestion]


def _get_candidate_variant(db: Session, current_user: User, variant_id: UUID):
    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    if variant is None:
        raise HTTPException(404, "variant not found")

    assignment = (
        db.query(CandidateAssignment)
        .filter(CandidateAssignment.user_id == current_user.id,
                CandidateAssignment.exam_event_id == variant.exam_event_id)
        .first()
    )
    if assignment is None:
        raise HTTPException(403, "you are not assigned to this exam event")

    variant_assignment = (
        db.query(VariantAssignment)
        .filter(VariantAssignment.centre_id == assignment.centre_id, VariantAssignment.variant_id == variant.id)
        .first()
    )
    if variant_assignment is None:
        raise HTTPException(403, "this variant was not assigned to your centre")

    return variant


@router.get("/me/paper/{variant_id}", response_model=DeliveredPaperOut)
def my_paper(
    variant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT])),
):
    variant = _get_candidate_variant(db, current_user, variant_id)
    event = db.query(ExamEvent).filter(ExamEvent.id == variant.exam_event_id).first()

    exam_end_epoch = event.exam_start_epoch + (event.exam_duration_minutes * 60)
    now = time.time()
    if now < event.exam_start_epoch:
        raise HTTPException(403, "the exam has not started yet")
    if now > exam_end_epoch:
        raise HTTPException(403, "the exam window has closed")

    delivered = db.query(DeliveredPaper).filter(DeliveredPaper.variant_id == variant_id).first()
    if delivered is None:
        raise HTTPException(404, "the paper has not been delivered yet — ask your centre operator")

    return DeliveredPaperOut(
        variant_id=str(variant_id),
        exam_end_epoch=exam_end_epoch,
        questions=[DeliveredQuestion(**q) for q in delivered.questions_json],
    )


class SubmitAnswersRequest(BaseModel):
    variant_id: str
    answers: Dict[str, List[int]]  # question_id -> selected option indices


class SubmitAnswersResponse(BaseModel):
    submitted_at: float


@router.post("/me/submit", response_model=SubmitAnswersResponse)
def submit_answers(
    req: SubmitAnswersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT])),
):
    variant_id = UUID(req.variant_id)
    variant = _get_candidate_variant(db, current_user, variant_id)
    event = db.query(ExamEvent).filter(ExamEvent.id == variant.exam_event_id).first()

    exam_end_epoch = event.exam_start_epoch + (event.exam_duration_minutes * 60)
    if time.time() > exam_end_epoch:
        raise HTTPException(403, "the exam window has closed — submission rejected")

    existing = (
        db.query(CandidateSubmission)
        .filter(CandidateSubmission.candidate_user_id == current_user.id,
                CandidateSubmission.variant_id == variant_id)
        .first()
    )
    if existing is not None:
        raise HTTPException(400, "you have already submitted this exam")

    submission = CandidateSubmission(
        candidate_user_id=current_user.id, variant_id=variant_id, answers_json=req.answers,
    )
    db.add(submission)
    db.flush()

    ledger_service.append(
        db, LedgerEventType.EXAM_SUBMITTED,
        details={"variant_id": str(variant_id), "candidate_id": str(current_user.id),
                  "num_answers": len(req.answers)},
        actor_id=current_user.id, exam_event_id=event.id,
    )
    db.commit()
    db.refresh(submission)

    return SubmitAnswersResponse(submitted_at=submission.submitted_at.timestamp())