import time
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.config import settings
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.custodian import Custodian
from app.models.share_submission import SubmissionType
from app.models.paper_variant import PaperVariant
from app.models.exam_event import ExamEvent
from app.models.exam_centre import ExamCentre
from app.services import custodian_service, access_control, print_service

router = APIRouter(prefix="/variants", tags=["variants"])


@router.get("/{variant_id}/status")
def variant_status(variant_id: UUID, db: Session = Depends(get_db),
                    current_user: User = Depends(require_role(list(UserRole)))):
    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    if variant is None:
        raise HTTPException(404, "variant not found")
    event = db.query(ExamEvent).filter(ExamEvent.id == variant.exam_event_id).first()

    standard_shares = custodian_service._get_submitted_shares(db, variant_id, SubmissionType.STANDARD)
    override_shares = custodian_service._get_submitted_shares(db, variant_id, SubmissionType.OVERRIDE)
    now = time.time()

    return {
        "variant_id": str(variant_id),
        "shares_submitted": len(standard_shares),
        "threshold_required": event.threshold,
        "override_shares_submitted": len(override_shares),
        "override_threshold_required": event.override_threshold,
        "exam_start_epoch": event.exam_start_epoch,
        "override_window_end_epoch": event.override_window_end_epoch,
        "seconds_until_exam": max(0, event.exam_start_epoch - now),
        "can_unlock_standard": len(standard_shares) >= event.threshold and now >= event.exam_start_epoch,
        "can_unlock_override": len(override_shares) >= event.override_threshold and now >= event.exam_start_epoch,
    }


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
    access_result = access_control.check_access(
        db, current_user, action="submit_share",
        allowed_roles=[UserRole.CUSTODIAN],
        now_epoch=time.time(),
        device_fingerprint=req.device_fingerprint,
        location_required=False,
        time_window_required=True,
        window_start=0,
        window_end=event.override_window_end_epoch,
    )
    if not access_result.overall_passed:
        db.commit()
        raise HTTPException(403, access_result.reason)

    custodian_service.submit_share(
        db, variant_id, custodian.id,
        req.submission_type, ntp_verified_time=time.time(),
    )
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

    print_job_id = None
    if result.status == "unlocked":
        jobs = print_service.dispatch_print_jobs(
            db, variant_id=variant_id, centre_id=centre.id,
            total_copies=centre.expected_candidate_count,
            num_printers=4,
        )
        db.commit()
        print_job_id = str(jobs[0].id) if jobs else None

    return {
        "status": result.status,
        "reason": result.reason,
        "paper_text": result.paper_text.decode() if result.paper_text else None,
        "print_job_id": print_job_id,
    }