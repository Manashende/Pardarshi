import time
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.config import settings
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.custodian import Custodian
from sqlalchemy import func, and_
from app.models.share_submission import SubmissionType, ShareSubmission
from app.models.custodian_variant_share import CustodianVariantShare
from app.models.paper_variant import PaperVariant
from app.models.exam_event import ExamEvent, DeliveryMode
from app.models.exam_centre import ExamCentre
from app.models.question import Question
from app.models.centre_operator_assignment import CentreOperatorAssignment
from app.models.variant_assignment import VariantAssignment
from app.models.ledger_entry import LedgerEventType
from app.services import custodian_service, access_control, print_service, ledger_service
from app.services import delivery_service

router = APIRouter(prefix="/variants", tags=["variants"])


@router.get("/{variant_id}/status")
def variant_status(variant_id: UUID, db: Session = Depends(get_db),
                    current_user: User = Depends(require_role(list(UserRole)))):
    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    if variant is None:
        raise HTTPException(404, "variant not found")
    event = db.query(ExamEvent).filter(ExamEvent.id == variant.exam_event_id).first()

    now = time.time()
    count_rows = (
        db.query(
            ShareSubmission.submission_type,
            func.count(func.distinct(ShareSubmission.custodian_id)),
        )
        .select_from(ShareSubmission)
        .join(Custodian, Custodian.id == ShareSubmission.custodian_id)
        .join(
            CustodianVariantShare,
            and_(
                CustodianVariantShare.custodian_id == ShareSubmission.custodian_id,
                CustodianVariantShare.variant_id == ShareSubmission.variant_id,
            ),
        )
        .filter(ShareSubmission.variant_id == variant_id)
        .group_by(ShareSubmission.submission_type)
        .all()
    )
    count_by_type = {st: n for st, n in count_rows}
    standard_count = count_by_type.get(SubmissionType.STANDARD, 0)
    override_count = count_by_type.get(SubmissionType.OVERRIDE, 0)

    return {
        "variant_id": str(variant_id),
        "shares_submitted": standard_count,
        "threshold_required": event.threshold,
        "override_shares_submitted": override_count,
        "override_threshold_required": event.override_threshold,
        "exam_start_epoch": event.exam_start_epoch,
        "override_window_end_epoch": event.override_window_end_epoch,
        "seconds_until_exam": max(0, event.exam_start_epoch - now),
        "can_unlock_standard": standard_count >= event.threshold and now >= event.exam_start_epoch,
        "can_unlock_override": override_count >= event.override_threshold and now >= event.exam_start_epoch,
    }


class VariantQuestionOut(BaseModel):
    question_id: str
    position: int  # 1-based index in this variant's FIXED question order
    topic: str
    difficulty: str
    question_type: str
    tags: List[str]


@router.get("/{variant_id}/questions", response_model=List[VariantQuestionOut])
def list_variant_questions(
    variant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """
    Metadata ONLY for the questions compiled into this specific variant,
    in the exact fixed order every candidate on it saw them (verified:
    delivery_service never reshuffles per-candidate, so this order is
    identical for CBT and PRINT). This position is what lets an
    investigator map "the leaked paper's Question 7" back to a real
    question_id — never question_text, options, or contributor identity,
    which only unlocks via the separate dual-control flow in
    app/api/question_reveal.py.
    """
    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    if variant is None:
        raise HTTPException(404, "variant not found")

    question_ids = [UUID(qid) for qid in (variant.question_ids or [])]
    questions_by_id = {q.id: q for q in db.query(Question).filter(Question.id.in_(question_ids)).all()}

    result = []
    for position, qid in enumerate(question_ids, start=1):
        q = questions_by_id.get(qid)
        if q is None:
            continue  # a single missing row should never break the whole listing
        result.append(VariantQuestionOut(
            question_id=str(q.id), position=position, topic=q.topic,
            difficulty=q.difficulty.value, question_type=q.question_type.value, tags=q.tags,
        ))
    return result


class SubmitShareRequest(BaseModel):
    x: int
    y: str
    submission_type: SubmissionType
    declared_latitude: float
    declared_longitude: float
    device_fingerprint: str


@router.post("/{variant_id}/submit-share")
def submit_share(
    variant_id: UUID, req: SubmitShareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.CUSTODIAN])),
):
    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    if variant is None:
        raise HTTPException(404, "variant not found")

    custodian = (
        db.query(Custodian)
        .filter(Custodian.exam_event_id == variant.exam_event_id, Custodian.user_id == current_user.id)
        .first()
    )
    if custodian is None:
        raise HTTPException(403, "you are not an assigned custodian for this exam event")

    event = db.query(ExamEvent).filter(ExamEvent.id == variant.exam_event_id).first()

    # Algorithm D: role + device + time-window. Location is intentionally
    # skipped (location_required=False) — Custodian doesn't yet have a
    # registered office lat/lon in the data model, so there's nothing
    # correct to check against. Adding Custodian.expected_latitude/
    # longitude is real follow-up work if you want full four-condition
    # coverage on this action.
    # The two submission types have opposite windows around the same
    # deadline: standard closes at override_window_end_epoch, override
    # opens there. Previously both used (0 -> deadline), so once the
    # override path became relevant this check blocked it.
    if req.submission_type == SubmissionType.OVERRIDE:
        window_start = event.override_window_end_epoch
        window_end = float("inf")  # no upper bound; attempt_unlock has none either
    else:
        window_start = 0
        window_end = event.override_window_end_epoch

    access_result = access_control.check_access(
        db, current_user, action="submit_share",
        allowed_roles=[UserRole.CUSTODIAN],
        now_epoch=time.time(),
        device_fingerprint=req.device_fingerprint,
        location_required=False,
        time_window_required=True,
        window_start=window_start,
        window_end=window_end,
    )
    if not access_result.overall_passed:
        db.commit()
        raise HTTPException(403, access_result.reason)

    try:
        custodian_service.submit_share(
            db, variant_id, custodian.id,
            req.submission_type, ntp_verified_time=time.time(),
            claimed_x=req.x, claimed_y=req.y,
        )
    except custodian_service.ShareMismatchError as e:
        raise HTTPException(403, str(e))
    db.commit()
    return variant_status(variant_id, db, current_user)


class UnlockRequest(BaseModel):
    centre_id: str
    declared_latitude: float
    declared_longitude: float
    device_fingerprint: str


@router.post("/{variant_id}/unlock")
def unlock(
    variant_id: UUID, req: UnlockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.CENTRE_OPERATOR])),
):
    centre = db.query(ExamCentre).filter(ExamCentre.id == UUID(req.centre_id)).first()
    if centre is None:
        raise HTTPException(404, "centre not found")
    
        # The operator must be assigned to THIS centre, and the variant must have
    # been assigned to THIS centre at compile time.
    operator_assigned = (
        db.query(CentreOperatorAssignment)
        .filter(CentreOperatorAssignment.user_id == current_user.id,
                CentreOperatorAssignment.centre_id == centre.id)
        .first()
    )
    variant_assigned = (
        db.query(VariantAssignment)
        .filter(VariantAssignment.variant_id == variant_id,
                VariantAssignment.centre_id == centre.id)
        .first()
    )
    if operator_assigned is None or variant_assigned is None:
        reason = ("operator is not assigned to this centre" if operator_assigned is None
                  else "this variant is not assigned to this centre")
        ledger_service.append(
            db, LedgerEventType.ACCESS_DENIED,
            details={"action": "request_decrypt", "reason": reason,
                     "variant_id": str(variant_id), "centre_id": str(centre.id)},
            actor_id=current_user.id,
        )
        db.commit()
        raise HTTPException(403, reason)

    # Algorithm D: role + device + location (vs THIS centre). Time-window
    # is deliberately NOT enforced here — the precise, NTP-verified
    # time-lock (Algorithm C) happens inside custodian_service.attempt_unlock
    # below; this gate is the broader "are you even allowed to be here
    # asking" check, not a substitute for that.
    access_result = access_control.check_access(
        db, current_user, action="request_decrypt",
        allowed_roles=[UserRole.CENTRE_OPERATOR],
        now_epoch=time.time(),
        device_fingerprint=req.device_fingerprint,
        declared_lat=req.declared_latitude, declared_lon=req.declared_longitude,
        expected_lat=centre.latitude, expected_lon=centre.longitude,
        acceptable_radius_m=centre.acceptable_radius_m,
        location_required=True,
        time_window_required=False,
    )
    if not access_result.overall_passed:
        db.commit()
        raise HTTPException(403, access_result.reason)

    result = custodian_service.attempt_unlock(
        db, variant_id, ntp_servers=settings.ntp_server_list,
        centre_id=centre.id,
    )

    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    if variant is None:
        raise HTTPException(404, "variant not found")
    exam_event = db.query(ExamEvent).filter(ExamEvent.id == variant.exam_event_id).first()

    print_job_id = None
    delivered_to_candidates = False
    if result.status == "unlocked":
        if exam_event.delivery_mode == DeliveryMode.PRINT:
            jobs = print_service.dispatch_print_jobs(
                db, variant_id=variant_id, centre_id=centre.id,
                total_copies=centre.expected_candidate_count,
                num_printers=centre.num_printers,
            )
            db.commit()
            print_job_id = str(jobs[0].id) if jobs else None
        else:
            delivery_service.deliver_to_candidates(db, variant_id=variant_id, paper_text=result.paper_text)
            db.commit()
            delivered_to_candidates = True

    return {
        "status": result.status,
        "reason": result.reason,
        "print_job_id": print_job_id,
        "delivered_to_candidates": delivered_to_candidates,
    }