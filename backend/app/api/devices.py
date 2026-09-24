"""
Device registration. A user registers their own device fingerprint, but
it starts INACTIVE — an admin must approve it before it counts for the
Algorithm D device check. Self-registration without approval would
defeat the purpose of the check.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.device import Device
from app.models.ledger_entry import LedgerEventType
from app.services import ledger_service

router = APIRouter(prefix="/devices", tags=["devices"])


class RegisterDeviceRequest(BaseModel):
    fingerprint: str


class DeviceOut(BaseModel):
    id: str
    user_id: str
    fingerprint: str
    is_active: bool


@router.post("/register", response_model=DeviceOut)
def register_device(
    req: RegisterDeviceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (
        db.query(Device)
        .filter(Device.user_id == current_user.id, Device.fingerprint == req.fingerprint)
        .first()
    )
    if existing:
        return DeviceOut(
            id=str(existing.id), user_id=str(existing.user_id),
            fingerprint=existing.fingerprint, is_active=existing.is_active,
        )

    device = Device(user_id=current_user.id, fingerprint=req.fingerprint, is_active=False)
    db.add(device)
    db.commit()
    db.refresh(device)
    return DeviceOut(id=str(device.id), user_id=str(device.user_id), fingerprint=device.fingerprint, is_active=device.is_active)


@router.get("/pending", response_model=list[DeviceOut])
def list_pending_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    devices = db.query(Device).filter(Device.is_active == False).all()  # noqa: E712
    return [
        DeviceOut(id=str(d.id), user_id=str(d.user_id), fingerprint=d.fingerprint, is_active=d.is_active)
        for d in devices
    ]


@router.post("/{device_id}/approve", response_model=DeviceOut)
def approve_device(
    device_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        raise HTTPException(404, "device not found")
        
    device.is_active = True
    
    # Append the action to the cryptographic audit ledger
    ledger_service.append(
        db,
        LedgerEventType.OVERRIDE_APPROVED,
        details={
            "action": "DEVICE_APPROVED",
            "target": device.fingerprint,
            "message": f"Administrator approved device: {device.fingerprint}"
        },
        actor_id=current_user.id
    )
    
    db.commit()
    db.refresh(device)
    return DeviceOut(id=str(device.id), user_id=str(device.user_id), fingerprint=device.fingerprint, is_active=device.is_active)