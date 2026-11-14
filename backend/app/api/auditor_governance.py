"""
Auditor account governance — applies the same no-single-party-trust
principle Shamir's Secret Sharing already applies to cryptographic
access, here to WHO GETS TO BECOME AN AUDITOR. Admin approving Auditor
accounts would let the party being audited control who audits them,
defeating the entire point of an independent oversight role.

Rule: a pending AUDITOR-role account needs AUDITOR_APPROVAL_THRESHOLD
distinct votes from EXISTING ACTIVE Auditors before it activates. Admin
has NO path to approve an Auditor account through this router at all —
that guard lives in app/api/users.py's approve_user, which only permits
Admin to act on an AUDITOR-role account during the one-time bootstrap
window (while zero active Auditors exist yet). Once even one Auditor
exists, Admin is permanently locked out of this decision.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.auditor_approval_vote import AuditorApprovalVote
from app.models.ledger_entry import LedgerEventType
from app.services import ledger_service

router = APIRouter(prefix="/auditor-governance", tags=["auditor-governance"])

# Same minimal-but-genuine dual-control principle used elsewhere in this
# system (e.g. PRINT mode's required_officials_count) — two distinct
# people must independently agree, not one.
AUDITOR_APPROVAL_THRESHOLD = 2


class PendingAuditorOut(BaseModel):
    user_id: str
    email: str
    full_name: str
    votes_cast: int
    votes_required: int
    already_voted_by_me: bool


@router.get("/pending", response_model=List[PendingAuditorOut])
def list_pending_auditors(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.AUDITOR])),
):
    pending_users = (
        db.query(User)
        .filter(User.role == UserRole.AUDITOR, User.is_active == False)  # noqa: E712
        .all()
    )
    result = []
    for u in pending_users:
        votes = db.query(AuditorApprovalVote).filter(AuditorApprovalVote.pending_user_id == u.id).all()
        already_voted = any(v.voting_auditor_id == current_user.id for v in votes)
        result.append(PendingAuditorOut(
            user_id=str(u.id), email=u.email, full_name=u.full_name,
            votes_cast=len(votes), votes_required=AUDITOR_APPROVAL_THRESHOLD,
            already_voted_by_me=already_voted,
        ))
    return result


@router.post("/{user_id}/vote", response_model=PendingAuditorOut)
def vote_to_approve_auditor(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.AUDITOR])),
):
    pending_user = db.query(User).filter(User.id == user_id).first()
    if pending_user is None:
        raise HTTPException(404, "user not found")
    if pending_user.role != UserRole.AUDITOR:
        raise HTTPException(400, "this endpoint only handles AUDITOR-role approvals")
    if pending_user.is_active:
        raise HTTPException(400, "this account is already active")

    existing_vote = (
        db.query(AuditorApprovalVote)
        .filter(AuditorApprovalVote.pending_user_id == pending_user.id,
                AuditorApprovalVote.voting_auditor_id == current_user.id)
        .first()
    )
    if existing_vote is None:
        vote = AuditorApprovalVote(pending_user_id=pending_user.id, voting_auditor_id=current_user.id)
        db.add(vote)
        ledger_service.append(
            db, LedgerEventType.AUDITOR_APPROVAL_VOTE_CAST,
            details={"pending_user_id": str(pending_user.id), "voting_auditor_id": str(current_user.id)},
            actor_id=current_user.id,
        )
        db.commit()

    votes = db.query(AuditorApprovalVote).filter(AuditorApprovalVote.pending_user_id == pending_user.id).all()

    if len(votes) >= AUDITOR_APPROVAL_THRESHOLD and not pending_user.is_active:
        pending_user.is_active = True
        ledger_service.append(
            db, LedgerEventType.AUDITOR_APPROVED,
            details={
                "approved_user_id": str(pending_user.id),
                "approving_auditor_ids": [str(v.voting_auditor_id) for v in votes],
            },
            actor_id=None,
        )
        db.commit()
        db.refresh(pending_user)

    return PendingAuditorOut(
        user_id=str(pending_user.id), email=pending_user.email, full_name=pending_user.full_name,
        votes_cast=len(votes), votes_required=AUDITOR_APPROVAL_THRESHOLD,
        already_voted_by_me=True,
    )