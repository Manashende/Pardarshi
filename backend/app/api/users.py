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
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR])),
):
    """
    Excludes pending AUDITOR-role accounts from Admin's queue entirely —
    those go through /auditor-governance instead, voted on by existing
    Auditors, NOT Admin — UNLESS this is the one-time bootstrap window
    (zero active Auditors exist yet), in which case Admin sees them here
    since there's no one else who could possibly approve the very first
    one.
    """
    active_auditor_count = (
        db.query(User).filter(User.role == UserRole.AUDITOR, User.is_active == True).count()  # noqa: E712
    )
    query = db.query(User).filter(User.is_active == False)  # noqa: E712
    if active_auditor_count > 0:
        query = query.filter(User.role != UserRole.AUDITOR)
    users = query.all()
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

    if user.role == UserRole.AUDITOR:
        active_auditor_count = (
            db.query(User).filter(User.role == UserRole.AUDITOR, User.is_active == True).count()  # noqa: E712
        )
        if active_auditor_count > 0:
            raise HTTPException(
                403,
                "Auditor accounts require consensus from existing Auditors, not Admin approval — "
                "see /auditor-governance/pending. Admin can only approve the very first Auditor account.",
            )
        # Bootstrap exception — logged as its own distinct event type so
        # it's permanently visible as the documented one-time exception
        # it is, never indistinguishable from ordinary approvals.
        ledger_service.append(
            db, LedgerEventType.AUDITOR_BOOTSTRAP_APPROVED,
            details={
                "approved_user_id": str(user.id), "approved_user_email": user.email,
                "approved_by_admin_email": current_user.email,
            },
            actor_id=current_user.id,
        )
    else:
        ledger_service.append(
            db, LedgerEventType.USER_APPROVED,
            details={
                "approved_user_id": str(user.id), "approved_user_email": user.email,
                "approved_user_role": user.role.value,
                "approved_by_admin_email": current_user.email,
            },
            actor_id=current_user.id,
        )

    user.is_active = True
    db.commit()
    db.refresh(user)
    return UserOut(id=str(user.id), email=user.email, full_name=user.full_name, role=user.role.value, is_active=user.is_active)