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

import time
from sqlalchemy import func, and_

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.core import share_crypto
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
    now = time.time()

    custodian_rows = db.query(Custodian).filter(Custodian.user_id == current_user.id).all()
    if not custodian_rows:
        return []

    # --- Batched loading: a handful of queries total, not per event/variant ---
    event_ids = [c.exam_event_id for c in custodian_rows]
    events = {
        e.id: e
        for e in db.query(ExamEvent).filter(ExamEvent.id.in_(event_ids)).all()
    }

    variants = (
        db.query(PaperVariant)
        .filter(PaperVariant.exam_event_id.in_(event_ids))
        .order_by(PaperVariant.variant_index)
        .all()
    )
    variants_by_event = {}
    for v in variants:
        variants_by_event.setdefault(v.exam_event_id, []).append(v)
    variant_ids = [v.id for v in variants]

    # One grouped query for ALL submission counts (distinct custodians per
    # variant and submission type). No share decryption needed to count.
    counts = {}
    if variant_ids:
        count_rows = (
            db.query(
                ShareSubmission.variant_id,
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
            .filter(ShareSubmission.variant_id.in_(variant_ids))
            .group_by(ShareSubmission.variant_id, ShareSubmission.submission_type)
            .all()
        )
        for vid, st, n in count_rows:
            counts[(vid, st)] = n

    # This custodian's own submissions, one query for every event.
    own_custodian_ids = [c.id for c in custodian_rows]
    own_rows = (
        db.query(ShareSubmission.variant_id, ShareSubmission.submission_type)
        .filter(ShareSubmission.custodian_id.in_(own_custodian_ids))
        .all()
    )
    own_submitted_set = {(vid, st) for vid, st in own_rows}

    result = []
    for custodian in custodian_rows:
        event = events.get(custodian.exam_event_id)
        if event is None:
            continue

        variant_entries = []
        for v in variants_by_event.get(event.id, []):
            std = counts.get((v.id, SubmissionType.STANDARD), 0)
            ovr = counts.get((v.id, SubmissionType.OVERRIDE), 0)
            variant_entries.append(AssignedVariant(
                variant_id=str(v.id),
                variant_index=v.variant_index,
                shares_submitted=std,
                threshold_required=event.threshold,
                override_shares_submitted=ovr,
                override_threshold_required=event.override_threshold,
                exam_start_epoch=event.exam_start_epoch,
                override_window_end_epoch=event.override_window_end_epoch,
                seconds_until_exam=max(0, event.exam_start_epoch - now),
                can_unlock_standard=std >= event.threshold and now >= event.exam_start_epoch,
                can_unlock_override=ovr >= event.override_threshold and now >= event.exam_start_epoch,
                has_submitted_standard=(v.id, SubmissionType.STANDARD) in own_submitted_set,
                has_submitted_override=(v.id, SubmissionType.OVERRIDE) in own_submitted_set,
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

    return MyShareResponse(x=custodian.share_x, y=str(share_crypto.decrypt_share_value(variant_share.share_y_encrypted)))