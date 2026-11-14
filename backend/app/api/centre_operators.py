"""
Centre-Operator assignment management + self-discovery.

Mirrors the pattern established for Custodian in app/api/custodians.py:
admin creates the assignment, the assigned user can discover what they're
tied to, and unlock's access check (see the fix in app/api/variants.py)
verifies against this table instead of trusting the request body.
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
from app.models.exam_centre import ExamCentre
from app.models.exam_event import ExamEvent
from app.models.paper_variant import PaperVariant
from app.models.variant_assignment import VariantAssignment
from app.models.centre_operator_assignment import CentreOperatorAssignment
from app.models.official_presence_confirmation import OfficialPresenceConfirmation
from app.models.delivered_paper import DeliveredPaper
from app.models.print_job import PrintJob

router = APIRouter(prefix="/centre-operators", tags=["centre-operators"])


# ---------------------------------------------------------------------------
# Admin: create + list assignments
# ---------------------------------------------------------------------------

class AssignOperatorRequest(BaseModel):
    user_id: str
    centre_id: str


class AssignmentOut(BaseModel):
    id: str
    user_id: str
    user_email: str
    centre_id: str
    centre_code: str
    centre_name: str


@router.post("/assign", response_model=AssignmentOut)
def assign_operator(
    req: AssignOperatorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    user = db.query(User).filter(User.id == UUID(req.user_id)).first()
    if user is None:
        raise HTTPException(404, "user not found")
    if user.role != UserRole.CENTRE_OPERATOR:
        raise HTTPException(400, "user does not have the CENTRE_OPERATOR role")

    centre = db.query(ExamCentre).filter(ExamCentre.id == UUID(req.centre_id)).first()
    if centre is None:
        raise HTTPException(404, "centre not found")

    existing = (
        db.query(CentreOperatorAssignment)
        .filter(CentreOperatorAssignment.user_id == user.id, CentreOperatorAssignment.centre_id == centre.id)
        .first()
    )
    if existing is None:
        existing = CentreOperatorAssignment(user_id=user.id, centre_id=centre.id)
        db.add(existing)
        db.commit()
        db.refresh(existing)

    return AssignmentOut(
        id=str(existing.id), user_id=str(user.id), user_email=user.email,
        centre_id=str(centre.id), centre_code=centre.centre_code, centre_name=centre.name,
    )


@router.get("/assignments", response_model=List[AssignmentOut])
def list_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR])),
):
    rows = db.query(CentreOperatorAssignment).all()
    result = []
    for row in rows:
        user = db.query(User).filter(User.id == row.user_id).first()
        centre = db.query(ExamCentre).filter(ExamCentre.id == row.centre_id).first()
        if user is None or centre is None:
            continue
        result.append(AssignmentOut(
            id=str(row.id), user_id=str(user.id), user_email=user.email,
            centre_id=str(centre.id), centre_code=centre.centre_code, centre_name=centre.name,
        ))
    return result


# ---------------------------------------------------------------------------
# Centre-Operator: discover own assignments
# ---------------------------------------------------------------------------

class AssignedVariantForCentre(BaseModel):
    exam_event_id: str
    exam_name: str
    exam_status: str
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
    delivery_mode: str
    # Only meaningful when delivery_mode == "PRINT".
    print_window_hours: int
    required_officials_count: int
    officials_confirmed_count: int
    print_release_epoch: float
    i_have_confirmed_presence: bool
    # Real, durable truth from the DB (not session-only frontend state) —
    # a CBT variant is delivered once, ever, via DeliveredPaper; a PRINT
    # variant is delivered once per centre via any PrintJob row for this
    # (variant, centre) pair. Either way, an already-delivered variant can
    # never legitimately be unlocked again for this centre.
    already_delivered: bool


class AssignedCentre(BaseModel):
    centre_id: str
    centre_code: str
    centre_name: str
    latitude: float
    longitude: float
    acceptable_radius_m: int
    assignments: List[AssignedVariantForCentre]


@router.get("/me/assignments", response_model=List[AssignedCentre])
def my_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.CENTRE_OPERATOR])),
):
    operator_rows = (
        db.query(CentreOperatorAssignment)
        .filter(CentreOperatorAssignment.user_id == current_user.id)
        .all()
    )

    result = []
    for op_row in operator_rows:
        centre = db.query(ExamCentre).filter(ExamCentre.id == op_row.centre_id).first()
        if centre is None:
            continue

        variant_assignments = (
            db.query(VariantAssignment)
            .filter(VariantAssignment.centre_id == centre.id)
            .all()
        )

        entries = []
        for va in variant_assignments:
            event = db.query(ExamEvent).filter(ExamEvent.id == va.exam_event_id).first()
            variant = db.query(PaperVariant).filter(PaperVariant.id == va.variant_id).first()
            if event is None or variant is None:
                continue
            # Reuses the same status computation /variants/{id}/status and
            # custodians.py's discovery endpoint both use.
            status = variants_api.variant_status(variant.id, db, current_user)

            officials_confirmed_count = 0
            i_have_confirmed_presence = False
            if event.delivery_mode.value == "PRINT":
                officials_confirmed_count = (
                    db.query(OfficialPresenceConfirmation)
                    .filter(OfficialPresenceConfirmation.exam_event_id == event.id,
                            OfficialPresenceConfirmation.centre_id == centre.id)
                    .count()
                )
                i_have_confirmed_presence = (
                    db.query(OfficialPresenceConfirmation)
                    .filter(OfficialPresenceConfirmation.exam_event_id == event.id,
                            OfficialPresenceConfirmation.centre_id == centre.id,
                            OfficialPresenceConfirmation.official_user_id == current_user.id)
                    .first()
                    is not None
                )

            if event.delivery_mode.value == "PRINT":
                already_delivered = (
                    db.query(PrintJob)
                    .filter(PrintJob.variant_id == variant.id, PrintJob.centre_id == centre.id)
                    .first()
                    is not None
                )
            else:
                already_delivered = (
                    db.query(DeliveredPaper)
                    .filter(DeliveredPaper.variant_id == variant.id)
                    .first()
                    is not None
                )

            entries.append(AssignedVariantForCentre(
                exam_event_id=str(event.id),
                exam_name=event.exam_name,
                exam_status=event.status.value,
                variant_id=status["variant_id"],
                variant_index=variant.variant_index,
                shares_submitted=status["shares_submitted"],
                threshold_required=status["threshold_required"],
                override_shares_submitted=status["override_shares_submitted"],
                override_threshold_required=status["override_threshold_required"],
                exam_start_epoch=status["exam_start_epoch"],
                override_window_end_epoch=status["override_window_end_epoch"],
                seconds_until_exam=status["seconds_until_exam"],
                can_unlock_standard=status["can_unlock_standard"],
                can_unlock_override=status["can_unlock_override"],
                delivery_mode=event.delivery_mode.value,
                print_window_hours=event.print_window_hours,
                required_officials_count=event.required_officials_count,
                officials_confirmed_count=officials_confirmed_count,
                print_release_epoch=event.exam_start_epoch - (event.print_window_hours * 3600),
                i_have_confirmed_presence=i_have_confirmed_presence,
                already_delivered=already_delivered,
            ))

        result.append(AssignedCentre(
            centre_id=str(centre.id),
            centre_code=centre.centre_code,
            centre_name=centre.name,
            latitude=centre.latitude,
            longitude=centre.longitude,
            acceptable_radius_m=centre.acceptable_radius_m,
            assignments=entries,
        ))

    return result