"""
Forensic contributor-identity reveal for the item bank — gated the same
way Auditor account approval already is (see
app/api/auditor_governance.py): no single party may unilaterally learn
who wrote a given question. This exists purely for post-leak
investigation — it is NOT a routine browsing feature, and it never
reveals encrypted_content, only contributor identity, for ONE specific
question at a time.

Flow: an Admin opens a request against a question_id with a reason.
QUESTION_REVEAL_APPROVAL_THRESHOLD distinct ACTIVE Auditors must vote to
approve it — Admin has no path to approve their own request, for the
same reason Admin cannot approve Auditor accounts (see
auditor_governance.py's own docstring): the party being investigated
should never control whether the investigation into it proceeds. Only
the ORIGINAL requesting Admin may then view the revealed identity —
each view is separately ledger-logged, distinct from the approval
itself, since approval and viewing are different moments of
accountability.
"""
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.question import Question
from app.models.question_reveal_request import QuestionRevealRequest
from app.models.question_reveal_vote import QuestionRevealVote
from app.models.ledger_entry import LedgerEventType
from app.services import ledger_service

router = APIRouter(prefix="/question-reveal", tags=["question-reveal"])

# Same minimal-but-genuine dual-control principle as AUDITOR_APPROVAL_THRESHOLD
# in auditor_governance.py — kept as a SEPARATE constant since there's no
# reason these two thresholds need to change together.
QUESTION_REVEAL_APPROVAL_THRESHOLD = 2


class CreateRevealRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class RevealRequestOut(BaseModel):
    request_id: str
    question_id: str
    requested_by_admin_id: str
    reason: str
    created_at: float
    votes_cast: int
    votes_required: int
    already_voted_by_me: bool
    is_approved: bool


class RevealedIdentityOut(BaseModel):
    request_id: str
    question_id: str
    contributor_name: str
    contributor_email: str


def _to_out(req: QuestionRevealRequest, votes: List[QuestionRevealVote], current_user: User) -> RevealRequestOut:
    return RevealRequestOut(
        request_id=str(req.id),
        question_id=str(req.question_id),
        requested_by_admin_id=str(req.requested_by_admin_id),
        reason=req.reason,
        created_at=req.created_at.timestamp() if req.created_at else 0,
        votes_cast=len(votes),
        votes_required=QUESTION_REVEAL_APPROVAL_THRESHOLD,
        already_voted_by_me=any(v.voting_auditor_id == current_user.id for v in votes),
        is_approved=req.approved_at is not None,
    )


@router.post("/{question_id}/request", response_model=RevealRequestOut)
def request_reveal(
    question_id: UUID,
    req: CreateRevealRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if question is None:
        raise HTTPException(404, "question not found")

    existing_open = (
        db.query(QuestionRevealRequest)
        .filter(QuestionRevealRequest.question_id == question_id, QuestionRevealRequest.approved_at.is_(None))
        .first()
    )
    if existing_open is not None:
        raise HTTPException(400, "a reveal request for this question is already pending")

    reveal_request = QuestionRevealRequest(
        question_id=question_id, requested_by_admin_id=current_user.id, reason=req.reason,
    )
    db.add(reveal_request)
    db.flush()

    ledger_service.append(
        db, LedgerEventType.QUESTION_REVEAL_REQUESTED,
        details={"question_id": str(question_id), "reason": req.reason},
        actor_id=current_user.id,
    )
    db.commit()
    db.refresh(reveal_request)
    return _to_out(reveal_request, [], current_user)


@router.get("/pending", response_model=List[RevealRequestOut])
def list_pending_reveal_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.AUDITOR])),
):
    pending = db.query(QuestionRevealRequest).filter(QuestionRevealRequest.approved_at.is_(None)).all()
    result = []
    for r in pending:
        votes = db.query(QuestionRevealVote).filter(QuestionRevealVote.reveal_request_id == r.id).all()
        result.append(_to_out(r, votes, current_user))
    return result


@router.get("/mine", response_model=List[RevealRequestOut])
def list_my_reveal_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    my_requests = (
        db.query(QuestionRevealRequest)
        .filter(QuestionRevealRequest.requested_by_admin_id == current_user.id)
        .order_by(QuestionRevealRequest.created_at.desc())
        .all()
    )
    result = []
    for r in my_requests:
        votes = db.query(QuestionRevealVote).filter(QuestionRevealVote.reveal_request_id == r.id).all()
        result.append(_to_out(r, votes, current_user))
    return result


@router.post("/{request_id}/vote", response_model=RevealRequestOut)
def vote_to_approve_reveal(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.AUDITOR])),
):
    reveal_request = db.query(QuestionRevealRequest).filter(QuestionRevealRequest.id == request_id).first()
    if reveal_request is None:
        raise HTTPException(404, "reveal request not found")
    if reveal_request.approved_at is not None:
        raise HTTPException(400, "this request has already been approved")

    existing_vote = (
        db.query(QuestionRevealVote)
        .filter(QuestionRevealVote.reveal_request_id == request_id, QuestionRevealVote.voting_auditor_id == current_user.id)
        .first()
    )
    if existing_vote is None:
        vote = QuestionRevealVote(reveal_request_id=request_id, voting_auditor_id=current_user.id)
        db.add(vote)
        ledger_service.append(
            db, LedgerEventType.QUESTION_REVEAL_VOTE_CAST,
            details={"request_id": str(request_id), "question_id": str(reveal_request.question_id),
                      "voting_auditor_id": str(current_user.id)},
            actor_id=current_user.id,
        )
        db.commit()

    votes = db.query(QuestionRevealVote).filter(QuestionRevealVote.reveal_request_id == request_id).all()

    if len(votes) >= QUESTION_REVEAL_APPROVAL_THRESHOLD and reveal_request.approved_at is None:
        reveal_request.approved_at = datetime.now(timezone.utc)
        ledger_service.append(
            db, LedgerEventType.QUESTION_REVEAL_APPROVED,
            details={
                "request_id": str(request_id), "question_id": str(reveal_request.question_id),
                "approving_auditor_ids": [str(v.voting_auditor_id) for v in votes],
            },
            actor_id=None,
        )
        db.commit()
        db.refresh(reveal_request)

    return _to_out(reveal_request, votes, current_user)


@router.get("/{request_id}", response_model=RevealedIdentityOut)
def view_revealed_identity(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    reveal_request = db.query(QuestionRevealRequest).filter(QuestionRevealRequest.id == request_id).first()
    if reveal_request is None:
        raise HTTPException(404, "reveal request not found")
    if reveal_request.requested_by_admin_id != current_user.id:
        raise HTTPException(403, "only the admin who requested this reveal may view it")
    if reveal_request.approved_at is None:
        votes_cast = db.query(QuestionRevealVote).filter(QuestionRevealVote.reveal_request_id == request_id).count()
        raise HTTPException(
            403,
            f"not yet approved — {votes_cast}/{QUESTION_REVEAL_APPROVAL_THRESHOLD} auditor votes so far",
        )

    question = db.query(Question).filter(Question.id == reveal_request.question_id).first()
    if question is None:
        raise HTTPException(404, "underlying question no longer exists")
    contributor = db.query(User).filter(User.id == question.contributor_id).first()
    if contributor is None:
        raise HTTPException(404, "contributor account no longer exists")

    if reveal_request.viewed_at is None:
        reveal_request.viewed_at = datetime.now(timezone.utc)
        reveal_request.viewed_by_admin_id = current_user.id

    ledger_service.append(
        db, LedgerEventType.QUESTION_REVEAL_VIEWED,
        details={"request_id": str(request_id), "question_id": str(question.id)},
        actor_id=current_user.id,
    )
    db.commit()

    return RevealedIdentityOut(
        request_id=str(reveal_request.id), question_id=str(question.id),
        contributor_name=contributor.full_name, contributor_email=contributor.email,
    )