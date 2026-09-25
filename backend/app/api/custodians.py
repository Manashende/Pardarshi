"""
Discovery + share-reveal endpoints for the CUSTODIAN role.

Nothing here changes the unlock/threshold logic in custodian_service.py —
this just gives a custodian a way to (a) see which exam events/variants
they're assigned to, and (b) retrieve their OWN share value automatically,
so submitting a share is a one-click action instead of requiring someone
to hand them x/y values out of band.

Scope note: /me/share/{variant_id} intentionally reveals a value ONLY to
the custodian it belongs to. This is not a new weakening of the
no-human-view guarantee — that guarantee is about the ASSEMBLED PAPER
(Module 1), not about a custodian's own share of it. A custodian is, by
design, supposed to hold their own share; that's the whole premise of
threshold cryptography. This does intersect with Known Gap #1
(share_y_encrypted isn't actually encrypted at rest yet) — once that's
fixed, this endpoint is the one place that will need to decrypt using
something derived from the custodian's own credentials before returning
it, instead of just reading the stored value directly as it does now.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.api import variants as variants_api
from app.models.user import User, UserRole
from app.models.custodian import Custodian, CustodianType
from app.models.exam_event import ExamEvent
from app.models.paper_variant import PaperVariant
from app.models.custodian_variant_share import CustodianVariantShare
from app.models.share_submission import ShareSubmission, SubmissionType

router = APIRouter(prefix="/custodians", tags=["custodians"])


class AssignedVariant(BaseModel):
    variant_id: str
    variant_index: int
    shares_submitted: int
    threshold_required: int
    override_shares_submitted: int
    override_threshold_required: int
    exam_start_epoch: float
    override_window_end_epoch: float
    seconds_until_exam: float
    can_unlock_standard: bool
    can_unlock_override: bool
    has_submitted_standard: bool
    has_submitted_override: bool


class AssignedExamEvent(BaseModel):
    exam_event_id: str
    exam_name: str
    custodian_type: CustodianType
    status: str
    exam_start_epoch: float
    variants: List[AssignedVariant]


@router.get("/me/assignments", response_model=List[AssignedExamEvent])
def my_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.CUSTODIAN])),
):
    custodian_rows = db.query(Custodian).filter(Custodian.user_id == current_user.id).all()

    result = []
    for custodian in custodian_rows:
        event = db.query(ExamEvent).filter(ExamEvent.id == custodian.exam_event_id).first()
        if event is None:
            continue
        variants = (
            db.query(PaperVariant)
            .filter(PaperVariant.exam_event_id == event.id)
            .order_by(PaperVariant.variant_index)
            .all()
        )

        # Fetched ONCE per custodian (not per variant) — a set of
        # (variant_id, submission_type) this custodian has personally
        # submitted, so each variant row below is just an O(1) lookup
        # instead of two more queries per variant.
        own_submissions = (
            db.query(ShareSubmission.variant_id, ShareSubmission.submission_type)
            .filter(ShareSubmission.custodian_id == custodian.id)
            .all()
        )
        own_submitted_set = {(str(vid), st) for vid, st in own_submissions}

        variant_entries = []
        for v in variants:
            # Reuses the exact same status computation the /variants/{id}/status
            # route uses — calling the function directly (not via HTTP) since
            # it's a normal Python function; the Depends(...) defaults just
            # get overridden by the real db/current_user we already have.
            status = variants_api.variant_status(v.id, db, current_user)
            variant_entries.append(AssignedVariant(
                variant_id=status["variant_id"],
                variant_index=v.variant_index,
                shares_submitted=status["shares_submitted"],
                threshold_required=status["threshold_required"],
                override_shares_submitted=status["override_shares_submitted"],
                override_threshold_required=status["override_threshold_required"],
                exam_start_epoch=status["exam_start_epoch"],
                override_window_end_epoch=status["override_window_end_epoch"],
                seconds_until_exam=status["seconds_until_exam"],
                can_unlock_standard=status["can_unlock_standard"],
                can_unlock_override=status["can_unlock_override"],
                has_submitted_standard=(str(v.id), SubmissionType.STANDARD) in own_submitted_set,
                has_submitted_override=(str(v.id), SubmissionType.OVERRIDE) in own_submitted_set,
            ))
        result.append(AssignedExamEvent(
            exam_event_id=str(event.id),
            exam_name=event.exam_name,
            custodian_type=custodian.custodian_type,
            status=event.status.value,
            exam_start_epoch=event.exam_start_epoch,
            variants=variant_entries,
        ))
    return result


class MyShareResponse(BaseModel):
    x: int
    y: str


@router.get("/me/share/{variant_id}", response_model=MyShareResponse)
def my_share(
    variant_id: UUID,
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

    variant_share = (
        db.query(CustodianVariantShare)
        .filter(CustodianVariantShare.custodian_id == custodian.id, CustodianVariantShare.variant_id == variant_id)
        .first()
    )
    if variant_share is None:
        raise HTTPException(404, "no share has been generated for you on this variant yet")

    return MyShareResponse(x=custodian.share_x, y=variant_share.share_y_encrypted)