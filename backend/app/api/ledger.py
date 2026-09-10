from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.ledger_entry import LedgerEntry
from app.services import ledger_service

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("")
def get_ledger(db: Session = Depends(get_db),
               current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR]))):
    entries = db.query(LedgerEntry).order_by(LedgerEntry.index.asc()).all()
    return [
        {
            "index": e.index, "event_type": e.event_type.value,
            "actor_id": str(e.actor_id) if e.actor_id else None,
            "exam_event_id": str(e.exam_event_id) if e.exam_event_id else None,
            "details": e.details_json, "timestamp": e.timestamp.timestamp(),
            "prev_hash": e.prev_hash, "entry_hash": e.entry_hash,
        }
        for e in entries
    ]


@router.get("/verify")
def verify_ledger(db: Session = Depends(get_db),
                   current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR]))):
    return ledger_service.verify_chain(db)