"""
Module 4 — request the manual-override reconstruction path. This is a
LOGGING endpoint, not an unlock trigger — the actual override unlock
still goes through /variants/{id}/unlock, which already handles the
override path (higher threshold, past override_window_end_epoch) inside
custodian_service.attempt_unlock.

This exists so there's an explicit, auditable RECORD of why an override
was needed — useful for post-incident review.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.paper_variant import PaperVariant
from app.services import ledger_service
from app.models.ledger_entry import LedgerEventType

router = APIRouter(prefix="/variants", tags=["variants"])


class OverrideRequestBody(BaseModel):
    reason: str


@router.post("/{variant_id}/override-request")
def request_override(
    variant_id: UUID, req: OverrideRequestBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.CENTRE_OPERATOR, UserRole.ADMIN])),
):
    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    if variant is None:
        raise HTTPException(404, "variant not found")

    ledger_service.append(
        db, LedgerEventType.OVERRIDE_REQUESTED,
        details={"variant_id": str(variant_id), "reason": req.reason, "requested_by_role": current_user.role.value},
        actor_id=current_user.id, exam_event_id=variant.exam_event_id,
    )
    db.commit()

    return {"status": "override_requested", "variant_id": str(variant_id)}