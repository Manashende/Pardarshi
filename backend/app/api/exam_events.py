import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.exam_event import ExamEvent, ExamEventStatus, DeliveryMode
from app.models.exam_centre import ExamCentre
from app.models.paper_variant import PaperVariant
from app.models.custodian import Custodian, CustodianType
from app.models.variant_assignment import VariantAssignment
from app.models.question import QuestionDifficulty
from app.models.compile_proposal import CompileProposal
from app.services import compile_service, variant_assignment, ledger_service, item_bank_service
from app.models.ledger_entry import LedgerEventType

router = APIRouter(prefix="/exam-events", tags=["exam-events"])

IST_OFFSET = timedelta(hours=5, minutes=30)


def _exam_date_from_epoch(exam_start_epoch: float) -> str:
    """
    Derives the calendar date (IST) an exam falls on, from its
    exam_start_epoch — used as an input to Algorithm E's deterministic
    variant-to-centre assignment. This replaces having the proposing
    admin manually re-type a date that's already fixed by the exam's
    creator, which risked drifting out of sync with the actual
    exam_start_epoch. Hardcoded to IST since this project targets
    Indian exam boards; if that assumption changes, this is the one
    place to update it.
    """
    dt = datetime.fromtimestamp(exam_start_epoch, tz=timezone.utc) + IST_OFFSET
    return dt.strftime("%Y-%m-%d")


def _validate_centres_for_delivery_mode(db: Session, delivery_mode: DeliveryMode, centre_ids: List[str]) -> None:
    """
    A PRINT exam splits copies across a centre's printers at unlock time.
    A centre registered as CBT-only has zero printers, so unlock would
    fail on exam day after the paper was already reconstructed. Refuse
    that combination up front instead.
    """
    if delivery_mode != DeliveryMode.PRINT:
        return
    try:
        centre_uuids = [UUID(c) for c in centre_ids]
    except ValueError:
        raise HTTPException(400, "centre_ids contains an invalid centre id")
    centres = db.query(ExamCentre).filter(ExamCentre.id.in_(centre_uuids)).all()
    without_printers = [c.centre_code for c in centres if c.num_printers < 1]
    if without_printers:
        raise HTTPException(
            400,
            "PRINT exams can only use centres with at least one printer — "
            f"no printers registered at: {', '.join(without_printers)}",
        )


class CreateExamEventRequest(BaseModel):
    exam_name: str
    exam_start_epoch: float
    override_window_end_epoch: float
    exam_duration_minutes: int = 180
    num_variants: int
    questions_per_variant: int
    threshold: int
    total_custodians: int
    override_threshold: int
    delivery_mode: DeliveryMode = DeliveryMode.CBT
    print_window_hours: int = 2
    # A single official confirming their own presence defeats the whole
    # point of this check — PRINT mode's early-release accountability
    # relies on it being a genuinely DISTINCT, multi-person confirmation,
    # not one person vouching for themselves.
    required_officials_count: int = Field(default=2, gt=1)
    centre_ids: List[str]


@router.post("")
def create_exam_event(
    req: CreateExamEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    _validate_centres_for_delivery_mode(db, req.delivery_mode, req.centre_ids)

    secret = variant_assignment.generate_assignment_secret()
    secret_hash = variant_assignment.hash_secret_for_storage(secret)

    event = ExamEvent(
        exam_name=req.exam_name,
        exam_start_epoch=req.exam_start_epoch,
        override_window_end_epoch=req.override_window_end_epoch,
        exam_duration_minutes=req.exam_duration_minutes,
        num_variants=req.num_variants,
        questions_per_variant=req.questions_per_variant,
        centre_ids=req.centre_ids,
        threshold=req.threshold,
        total_custodians=req.total_custodians,
        override_threshold=req.override_threshold,
        assignment_secret_hash=secret_hash,
        status=ExamEventStatus.DRAFT,
        created_by=current_user.id,
        delivery_mode=req.delivery_mode,
        print_window_hours=req.print_window_hours,
        required_officials_count=req.required_officials_count,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # NOTE: the raw `secret` (not just its hash) is needed again at
    # confirm-compile time to actually compute assignments. For this
    # pass it's returned once here for the caller to hold onto — a
    # production version would want a proper secrets manager rather
    # than round-tripping it through the API response.
    return {"exam_event_id": str(event.id), "assignment_secret": secret.hex(), "delivery_mode": event.delivery_mode.value}


def _effective_status(event: ExamEvent, now: float) -> str:
    """
    LIVE/CLOSED are DISPLAY-ONLY derived states, never persisted — the
    stored `status` column only ever holds DRAFT, COMPILED, or CANCELLED.
    Whether a COMPILED exam currently counts as LIVE or CLOSED is purely
    a function of the clock, computed fresh on every read rather than
    written by a scheduled job (no such job exists in this codebase).
    This can never drift the way a missed cron run could.
    """
    if event.status != ExamEventStatus.COMPILED:
        return event.status.value
    exam_end_epoch = event.exam_start_epoch + (event.exam_duration_minutes * 60)
    if now < event.exam_start_epoch:
        return ExamEventStatus.COMPILED.value
    if now < exam_end_epoch:
        return ExamEventStatus.LIVE.value
    return ExamEventStatus.CLOSED.value


class ExamEventOut(BaseModel):
    id: str
    exam_name: str
    exam_start_epoch: float
    override_window_end_epoch: float
    num_variants: int
    questions_per_variant: int
    threshold: int
    total_custodians: int
    override_threshold: int
    delivery_mode: str
    print_window_hours: int
    required_officials_count: int
    exam_duration_minutes: int
    status: str  # raw persisted value — DRAFT/COMPILED/CANCELLED only
    effective_status: str  # display value — may show LIVE/CLOSED too
    centre_ids: List[str]
    created_by_is_self: bool


class VariantOut(BaseModel):
    variant_id: str
    variant_index: int
    num_questions: int


@router.get("/{exam_event_id}/variants", response_model=List[VariantOut])
def list_variants_for_exam_event(
    exam_event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR])),
):
    event = db.query(ExamEvent).filter(ExamEvent.id == exam_event_id).first()
    if event is None:
        raise HTTPException(404, "exam event not found")
    variants = (
        db.query(PaperVariant)
        .filter(PaperVariant.exam_event_id == exam_event_id)
        .order_by(PaperVariant.variant_index)
        .all()
    )
    return [
        VariantOut(variant_id=str(v.id), variant_index=v.variant_index, num_questions=len(v.question_ids or []))
        for v in variants
    ]


@router.get("", response_model=List[ExamEventOut])
def list_exam_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(list(UserRole))),
):
    events = db.query(ExamEvent).order_by(ExamEvent.exam_start_epoch.desc()).all()
    now = time.time()
    return [
        ExamEventOut(
            id=str(e.id), exam_name=e.exam_name, exam_start_epoch=e.exam_start_epoch,
            override_window_end_epoch=e.override_window_end_epoch, num_variants=e.num_variants,
            questions_per_variant=e.questions_per_variant,
            threshold=e.threshold, total_custodians=e.total_custodians,
            override_threshold=e.override_threshold, delivery_mode=e.delivery_mode.value,
            print_window_hours=e.print_window_hours, required_officials_count=e.required_officials_count,
            exam_duration_minutes=e.exam_duration_minutes, status=e.status.value,
            effective_status=_effective_status(e, now),
            centre_ids=e.centre_ids or [],
            created_by_is_self=(e.created_by == current_user.id),
        )
        for e in events
    ]


class EditExamEventRequest(BaseModel):
    exam_name: str
    exam_start_epoch: float
    override_window_end_epoch: float
    exam_duration_minutes: int
    num_variants: int
    questions_per_variant: int
    centre_ids: List[str]
    threshold: int
    total_custodians: int
    override_threshold: int
    delivery_mode: DeliveryMode = DeliveryMode.CBT
    print_window_hours: int = 2
    required_officials_count: int = Field(default=2, gt=1)


@router.put("/{exam_event_id}", response_model=ExamEventOut)
def edit_exam_event(
    exam_event_id: UUID,
    req: EditExamEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """
    Fixes a genuine data-entry mistake before anything real has
    happened — DRAFT only, and only before any admin has started a
    compile proposal against it (which references num_variants,
    threshold, etc. — changing those out from under an in-progress
    proposal would silently invalidate another admin's work).
    """
    event = db.query(ExamEvent).filter(ExamEvent.id == exam_event_id).first()
    if event is None:
        raise HTTPException(404, "exam event not found")
    if event.status != ExamEventStatus.DRAFT:
        raise HTTPException(400, f"exam event is '{event.status.value}' — only a DRAFT exam event can be edited")

    existing_proposal = db.query(CompileProposal).filter(CompileProposal.exam_event_id == exam_event_id).first()
    if existing_proposal is not None:
        raise HTTPException(
            400,
            "a compile has already been proposed for this exam — editing now would silently "
            "invalidate that admin's in-progress work",
        )

    _validate_centres_for_delivery_mode(db, req.delivery_mode, req.centre_ids)

    event.exam_name = req.exam_name
    event.exam_start_epoch = req.exam_start_epoch
    event.override_window_end_epoch = req.override_window_end_epoch
    event.exam_duration_minutes = req.exam_duration_minutes
    event.num_variants = req.num_variants
    event.questions_per_variant = req.questions_per_variant
    event.centre_ids = req.centre_ids
    event.threshold = req.threshold
    event.total_custodians = req.total_custodians
    event.override_threshold = req.override_threshold
    event.delivery_mode = req.delivery_mode
    event.print_window_hours = req.print_window_hours
    event.required_officials_count = req.required_officials_count

    ledger_service.append(
        db, LedgerEventType.EXAM_EVENT_EDITED,
        details={
            "exam_event_id": str(event.id), "exam_event_name": event.exam_name,
            "edited_by_admin_email": current_user.email,
        },
        actor_id=current_user.id, exam_event_id=event.id,
    )
    db.commit()
    db.refresh(event)

    now = time.time()
    return ExamEventOut(
        id=str(event.id), exam_name=event.exam_name, exam_start_epoch=event.exam_start_epoch,
        override_window_end_epoch=event.override_window_end_epoch, num_variants=event.num_variants,
        questions_per_variant=event.questions_per_variant, threshold=event.threshold,
        total_custodians=event.total_custodians, override_threshold=event.override_threshold,
        delivery_mode=event.delivery_mode.value, print_window_hours=event.print_window_hours,
        required_officials_count=event.required_officials_count, exam_duration_minutes=event.exam_duration_minutes,
        status=event.status.value, effective_status=_effective_status(event, now),
        centre_ids=event.centre_ids or [],
        created_by_is_self=(event.created_by == current_user.id),
    )


@router.post("/{exam_event_id}/cancel")
def cancel_exam_event(
    exam_event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """
    Cancels a mistakenly-created exam event — DRAFT only, never a
    compiled one. Compiling already produces real cryptographic
    material (encrypted variants, live custodian shares) and ledger
    entries referencing this exam_event_id; unwinding a compiled exam
    is an actual incident process, not a cancel button. Sets status to
    CANCELLED rather than deleting the row, so the ledger's references
    to it — and the row itself — stay intact, same never-destroy
    principle used everywhere else in this system.
    """
    event = db.query(ExamEvent).filter(ExamEvent.id == exam_event_id).first()
    if event is None:
        raise HTTPException(404, "exam event not found")
    if event.status != ExamEventStatus.DRAFT:
        raise HTTPException(
            400,
            f"exam event is '{event.status.value}' — only a DRAFT exam event can be cancelled. "
            "A compiled exam cannot be undone this way.",
        )

    event.status = ExamEventStatus.CANCELLED

    # A pending proposal for this event can now never be confirmed —
    # confirm_compile requires DRAFT — so it's permanently stale. Delete
    # it rather than leave a dead row behind; list_compile_proposals
    # already filters it out of view, but removing it here means there's
    # nothing lingering in the table for a cancelled event at all.
    stale_proposal = db.query(CompileProposal).filter(CompileProposal.exam_event_id == event.id).first()
    if stale_proposal is not None:
        db.delete(stale_proposal)

    ledger_service.append(
        db, LedgerEventType.EXAM_EVENT_CANCELLED,
        details={
            "exam_event_id": str(event.id), "exam_event_name": event.exam_name,
            "cancelled_by_admin_email": current_user.email,
        },
        actor_id=current_user.id, exam_event_id=event.id,
    )
    db.commit()
    return {"exam_event_id": str(event.id), "status": event.status.value}


# ---------------------------------------------------------------------------
# Compile: propose -> view -> confirm (dual-control, replaces the old
# single-shot /compile endpoint entirely). One Admin proposing and then
# immediately confirming their own proposal is deliberately blocked.
# ---------------------------------------------------------------------------

class ProposeCompileRequest(BaseModel):
    custodian_user_ids: List[str]
    custodian_types: List[str]
    difficulty_distribution: Optional[Dict[str, float]] = None
    subject_distribution: Optional[Dict[str, int]] = None


class CompileProposalOut(BaseModel):
    exam_event_id: str
    exam_name: str
    # Deliberately NO proposer identity here — see propose_compile's
    # docstring note. is_own_proposal is computed server-side relative
    # to whoever is CALLING this endpoint, so an admin can tell "is this
    # mine" without ever learning WHO a different admin's proposal
    # belongs to. The permanent ledger (VARIANTS_COMPILED's details)
    # still records both admins' real identities for post-hoc
    # accountability — this anonymity is scoped to the LIVE workflow
    # only, to prevent real-time collusion coordination through the
    # software itself, not to weaken retrospective audit.
    is_own_proposal: bool
    questions_per_variant: int
    custodian_user_ids: List[str]
    custodian_types: List[str]
    exam_date: str
    difficulty_distribution: Optional[Dict[str, float]]
    subject_distribution: Optional[Dict[str, int]]
    proposed_at: float


@router.post("/{exam_event_id}/propose-compile", response_model=CompileProposalOut)
def propose_compile(
    exam_event_id: UUID,
    req: ProposeCompileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    event = db.query(ExamEvent).filter(ExamEvent.id == exam_event_id).first()
    if event is None:
        raise HTTPException(404, "exam event not found")
    if event.status != ExamEventStatus.DRAFT:
        raise HTTPException(400, f"exam event is '{event.status.value}', can only propose a compile from DRAFT")
    if event.created_by == current_user.id:
        raise HTTPException(
            403,
            "you created this exam event — a different admin must propose its compile (and pick "
            "its custodians). This is a deliberate separation-of-duties check: the creator comes "
            "back later to confirm instead, so no single admin can both create an exam and choose "
            "its own custodian list.",
        )

    # Replaces any prior undecided proposal for this event — proposing
    # again always requires fresh confirmation from a (still different)
    # admin, even if the previous proposal was never confirmed.
    existing = db.query(CompileProposal).filter(CompileProposal.exam_event_id == exam_event_id).first()
    if existing is None:
        existing = CompileProposal(exam_event_id=exam_event_id)
        db.add(existing)

    existing.proposed_by_admin_id = current_user.id
    # Fixed by the exam's CREATOR at creation time, not the proposing
    # admin — the proposer only ever selects custodians.
    existing.questions_per_variant = event.questions_per_variant
    existing.custodian_user_ids = req.custodian_user_ids
    existing.custodian_types = req.custodian_types
    existing.exam_date = _exam_date_from_epoch(event.exam_start_epoch)
    existing.difficulty_distribution = req.difficulty_distribution
    existing.subject_distribution = req.subject_distribution

    # Human-readable snapshot captured NOW, alongside the raw IDs — not a
    # display-time lookup. See ledger_service.py's design note on why an
    # audit log must freeze names at write-time, not resolve them later.
    custodian_users = db.query(User).filter(User.id.in_([UUID(u) for u in req.custodian_user_ids])).all()
    email_by_id = {str(u.id): u.email for u in custodian_users}
    custodian_user_emails = [email_by_id.get(uid, uid) for uid in req.custodian_user_ids]

    ledger_service.append(
        db, LedgerEventType.COMPILE_PROPOSED,
        details={
            "exam_event_id": str(exam_event_id),
            "exam_event_name": event.exam_name,
            "custodian_user_ids": req.custodian_user_ids,
            "custodian_user_emails": custodian_user_emails,
            "custodian_types": req.custodian_types,
        },
        actor_id=current_user.id, exam_event_id=exam_event_id,
    )
    db.commit()
    db.refresh(existing)

    return CompileProposalOut(
        exam_event_id=str(exam_event_id),
        exam_name=event.exam_name,
        is_own_proposal=True,  # you just proposed it — trivially true
        questions_per_variant=existing.questions_per_variant,
        custodian_user_ids=existing.custodian_user_ids,
        custodian_types=existing.custodian_types,
        exam_date=existing.exam_date,
        difficulty_distribution=existing.difficulty_distribution,
        subject_distribution=existing.subject_distribution,
        proposed_at=existing.proposed_at.timestamp() if existing.proposed_at else time.time(),
    )


@router.get("/compile-proposals", response_model=List[CompileProposalOut])
def list_compile_proposals(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR])),
):
    """
    ALL pending compile proposals, across every exam event — this is
    what makes dual-control workable in practice rather than tedious:
    any admin sees this queue the moment they log in, same as Pending
    Approvals already works for user/device accounts. No side-channel
    communication ("hey, can you go approve my compile") is needed.
    """
    proposals = db.query(CompileProposal).all()
    result = []
    for p in proposals:
        event = db.query(ExamEvent).filter(ExamEvent.id == p.exam_event_id).first()
        # A proposal only makes sense while its exam event is still DRAFT —
        # confirm_compile itself enforces this same check. If the event was
        # cancelled (or somehow already compiled) after the proposal was
        # made, the proposal is stale: it can never be confirmed, so it
        # shouldn't sit in this "pending" list implying it can be acted on.
        if event is None or event.status != ExamEventStatus.DRAFT:
            continue
        result.append(CompileProposalOut(
            exam_event_id=str(p.exam_event_id),
            exam_name=event.exam_name,
            is_own_proposal=(p.proposed_by_admin_id == current_user.id),
            questions_per_variant=p.questions_per_variant,
            custodian_user_ids=p.custodian_user_ids,
            custodian_types=p.custodian_types,
            exam_date=p.exam_date,
            difficulty_distribution=p.difficulty_distribution,
            subject_distribution=p.subject_distribution,
            proposed_at=p.proposed_at.timestamp() if p.proposed_at else 0,
        ))
    return result


@router.get("/{exam_event_id}/compile-proposal", response_model=Optional[CompileProposalOut])
def get_compile_proposal(
    exam_event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Lets a DIFFERENT admin review a pending proposal before confirming it."""
    proposal = db.query(CompileProposal).filter(CompileProposal.exam_event_id == exam_event_id).first()
    if proposal is None:
        return None

    event = db.query(ExamEvent).filter(ExamEvent.id == exam_event_id).first()
    return CompileProposalOut(
        exam_event_id=str(exam_event_id),
        exam_name=event.exam_name,
        is_own_proposal=(proposal.proposed_by_admin_id == current_user.id),
        questions_per_variant=proposal.questions_per_variant,
        custodian_user_ids=proposal.custodian_user_ids,
        custodian_types=proposal.custodian_types,
        exam_date=proposal.exam_date,
        difficulty_distribution=proposal.difficulty_distribution,
        subject_distribution=proposal.subject_distribution,
        proposed_at=proposal.proposed_at.timestamp() if proposal.proposed_at else 0,
    )


class ConfirmCompileRequest(BaseModel):
    assignment_secret: str  # hex string returned by /exam-events on creation


@router.post("/{exam_event_id}/confirm-compile")
def confirm_compile(
    exam_event_id: UUID,
    req: ConfirmCompileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    event = db.query(ExamEvent).filter(ExamEvent.id == exam_event_id).first()
    if event is None:
        raise HTTPException(404, "exam event not found")
    if event.status != ExamEventStatus.DRAFT:
        raise HTTPException(400, f"exam event is '{event.status.value}', can only compile from DRAFT")

    proposal = db.query(CompileProposal).filter(CompileProposal.exam_event_id == exam_event_id).first()
    if proposal is None:
        raise HTTPException(400, "no compile proposal exists for this exam event yet — use /propose-compile first")
    if proposal.proposed_by_admin_id == current_user.id:
        raise HTTPException(
            403,
            "you proposed this compile — a DIFFERENT admin must confirm it. This is a deliberate "
            "dual-control check, not a bug: no single admin may unilaterally decide the custodian list.",
        )

    secret = bytes.fromhex(req.assignment_secret)
    custodian_types = [CustodianType(t) for t in proposal.custodian_types]

    # Custodian IDENTITY is created once for the whole exam event —
    # the same people serve every variant, each holding one fixed
    # x-coordinate. Their per-variant y-values are generated separately
    # below, inside compile_service.compile_variant, since each variant
    # has its own independent key.
    custodians = compile_service.get_or_create_custodians(
        db, exam_event_id=event.id,
        custodian_user_ids=[UUID(u) for u in proposal.custodian_user_ids],
        custodian_types=custodian_types,
    )

    parsed_distribution = None
    if proposal.difficulty_distribution:
        parsed_distribution = {
            QuestionDifficulty(k): v for k, v in proposal.difficulty_distribution.items()
        }

    # Module 1 — automated, no-human-view selection + assembly from the
    # encrypted item bank. Raises InsufficientQuestionsError if the bank
    # is too small; that propagates as a 400 below rather than silently
    # producing a short/broken paper.
    try:
        selection = item_bank_service.select_questions_for_variants(
            db, num_variants=event.num_variants, questions_per_variant=proposal.questions_per_variant,
            difficulty_distribution=parsed_distribution,
            subject_distribution=proposal.subject_distribution,
        )
    except item_bank_service.InsufficientQuestionsError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
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

    if not event.centre_ids:
        raise HTTPException(400, "this exam event has no centres selected — cannot compile")
    centres = db.query(ExamCentre).filter(ExamCentre.id.in_([UUID(c) for c in event.centre_ids])).all()
    assignments = []
    for centre in centres:
        a = variant_assignment.compute_assignment(secret, str(centre.id), proposal.exam_date, event.num_variants)
        variant = variants[a["variant_index"]]
        assignment = VariantAssignment(
            exam_event_id=event.id, centre_id=centre.id, variant_id=variant.id,
            assignment_hash=a["assignment_hash"],
        )
        db.add(assignment)
        assignments.append(assignment)

    event.status = ExamEventStatus.COMPILED
    proposed_by_user = db.query(User).filter(User.id == proposal.proposed_by_admin_id).first()
    # Records BOTH admins for full accountability — who proposed the
    # custodian list, and who confirmed it — not just whoever happened
    # to click the final button.
    ledger_service.append(db, LedgerEventType.VARIANTS_COMPILED, details={
        "exam_event_id": str(event.id), "exam_event_name": event.exam_name,
        "num_variants": event.num_variants,
        "num_centres_assigned": len(assignments),
        "proposed_by_admin_id": str(proposal.proposed_by_admin_id),
        "proposed_by_admin_email": proposed_by_user.email if proposed_by_user else None,
        "confirmed_by_admin_id": str(current_user.id),
        "confirmed_by_admin_email": current_user.email,
    }, actor_id=current_user.id, exam_event_id=event.id)

    db.delete(proposal)
    db.commit()

    return {
        "exam_event_id": str(event.id),
        "variants": [{"variant_id": str(v.id), "variant_index": v.variant_index} for v in variants],
        "assignments_created": len(assignments),
    }