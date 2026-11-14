"""
PRINT-mode accountability: on-site officials confirm physical presence
before printing/reconstruction is allowed to proceed. This is what
substitutes for CBT's strict exact-second time lock — instead of
"nobody can access this until the last possible instant", PRINT mode
allows earlier access IF enough named, identified people are physically
present and willing to be held accountable.
"""
import time
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.exam_event import ExamEvent, DeliveryMode
from app.models.exam_centre import ExamCentre
from app.models.centre_operator_assignment import CentreOperatorAssignment
from app.models.official_presence_confirmation import OfficialPresenceConfirmation
from app.models.ledger_entry import LedgerEventType
from app.services import access_control, ledger_service

router = APIRouter(prefix="/officials", tags=["officials"])


class ConfirmPresenceRequest(BaseModel):
    exam_event_id: str
    centre_id: str
    declared_latitude: float
    declared_longitude: float
    device_fingerprint: str


class PresenceStatus(BaseModel):
    exam_event_id: str
    centre_id: str
    required_officials_count: int
    confirmed_count: int
    confirmed_emails: List[str]
    satisfied: bool


def _build_status(db: Session, exam_event: ExamEvent, centre_id: UUID) -> PresenceStatus:
    confirmations = (
        db.query(OfficialPresenceConfirmation)
        .filter(OfficialPresenceConfirmation.exam_event_id == exam_event.id,
                OfficialPresenceConfirmation.centre_id == centre_id)
        .all()
    )
    emails = []
    for c in confirmations:
        user = db.query(User).filter(User.id == c.official_user_id).first()
        if user:
            emails.append(user.email)
    return PresenceStatus(
        exam_event_id=str(exam_event.id), centre_id=str(centre_id),
        required_officials_count=exam_event.required_officials_count,
        confirmed_count=len(confirmations), confirmed_emails=emails,
        satisfied=len(confirmations) >= exam_event.required_officials_count,
    )


@router.post("/confirm-presence", response_model=PresenceStatus)
def confirm_presence(
    req: ConfirmPresenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.CENTRE_OPERATOR])),
):
    exam_event = db.query(ExamEvent).filter(ExamEvent.id == UUID(req.exam_event_id)).first()
    if exam_event is None:
        raise HTTPException(404, "exam event not found")
    if exam_event.delivery_mode != DeliveryMode.PRINT:
        raise HTTPException(400, "presence confirmation only applies to PRINT-mode exam events")

    centre = db.query(ExamCentre).filter(ExamCentre.id == UUID(req.centre_id)).first()
    if centre is None:
        raise HTTPException(404, "centre not found")

    assignment = (
        db.query(CentreOperatorAssignment)
        .filter(CentreOperatorAssignment.user_id == current_user.id, CentreOperatorAssignment.centre_id == centre.id)
        .first()
    )
    if assignment is None:
        raise HTTPException(403, "you are not an assigned operator for this centre")

    access_result = access_control.check_access(
        db, current_user, action="confirm_presence",
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

    existing = (
        db.query(OfficialPresenceConfirmation)
        .filter(OfficialPresenceConfirmation.exam_event_id == exam_event.id,
                OfficialPresenceConfirmation.centre_id == centre.id,
                OfficialPresenceConfirmation.official_user_id == current_user.id)
        .first()
    )
    if existing is None:
        existing = OfficialPresenceConfirmation(
            exam_event_id=exam_event.id, centre_id=centre.id, official_user_id=current_user.id,
            declared_latitude=req.declared_latitude, declared_longitude=req.declared_longitude,
            device_fingerprint=req.device_fingerprint,
        )
        db.add(existing)
        ledger_service.append(
            db, LedgerEventType.OFFICIAL_PRESENCE_CONFIRMED,
            details={"exam_event_id": str(exam_event.id), "centre_id": str(centre.id),
                      "official_id": str(current_user.id)},
            actor_id=current_user.id, exam_event_id=exam_event.id,
        )
        db.commit()

    return _build_status(db, exam_event, centre.id)


@router.get("/status", response_model=PresenceStatus)
def presence_status(
    exam_event_id: str, centre_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.CENTRE_OPERATOR])),
):
    exam_event = db.query(ExamEvent).filter(ExamEvent.id == UUID(exam_event_id)).first()
    if exam_event is None:
        raise HTTPException(404, "exam event not found")
    return _build_status(db, exam_event, UUID(centre_id))