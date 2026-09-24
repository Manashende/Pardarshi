"""
Admin-side account approval — mirrors the device approval pattern.
Self-registered accounts start inactive; an admin must approve before
the account can log in.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.ledger_entry import LedgerEventType
from app.services import ledger_service

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool


@router.get("/pending", response_model=list[UserOut])
def list_pending_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    users = db.query(User).filter(User.is_active == False).all()  # noqa: E712
    return [UserOut(id=str(u.id), email=u.email, full_name=u.full_name, role=u.role.value, is_active=u.is_active) for u in users]


@router.get("", response_model=list[UserOut])
def list_users(
    role: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    query = db.query(User).filter(User.is_active == True)  # noqa: E712
    if role:
        query = query.filter(User.role == UserRole(role))
    users = query.order_by(User.full_name).all()
    return [UserOut(id=str(u.id), email=u.email, full_name=u.full_name, role=u.role.value, is_active=u.is_active) for u in users]


@router.post("/{user_id}/approve", response_model=UserOut)
def approve_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(404, "user not found")
    
    user.is_active = True
    
    # Append the action to the cryptographic audit ledger
    ledger_service.append(
        db,
        LedgerEventType.OVERRIDE_APPROVED, 
        details={
            "action": "ACCOUNT_APPROVED",
            "target": user.email,
            "message": f"Administrator approved account for {user.email}"
        },
        actor_id=current_user.id
    )
    
    db.commit()
    db.refresh(user)
    return UserOut(id=str(user.id), email=user.email, full_name=user.full_name, role=user.role.value, is_active=user.is_active)