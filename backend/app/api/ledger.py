from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.ledger_entry import LedgerEntry
from app.services import ledger_service

router = APIRouter(prefix="/ledger", tags=["ledger"])

# Keys ending in these suffixes directly name a real person (email/name) —
# stripped for Admin, since Admin is an operationally-interested party who
# could act on knowing exactly which named custodians/admins are tied to a
# given exam ahead of time (the same reason question_reveal.py requires
# independent Auditor approval before Admin can learn a contributor's
# identity). Auditor is the structurally independent oversight role this
# was always meant for, per ledger_service's original post-hoc-accountability
# intent — Auditor sees entries unredacted. The raw *_id fields stay visible
# to Admin either way; this only hides the human-readable convenience layer,
# not the underlying record itself.
# Only email-suffixed fields are treated as person-identifying — every
# genuinely personal field enriched so far (custodian_email,
# proposed_by_admin_email, device_owner_email, etc.) uses this suffix.
# A plain "_name" suffix is NOT included here on purpose: fields like
# exam_event_name or centre_name are organizational labels, not a
# person's identity, and should stay visible to Admin same as anywhere
# else in the app (the exam name is already shown openly on the Status
# tab). If a future field genuinely needs to pair a person with a
# "_name" (not "_email"), it should be renamed to end in "_email"
# instead, to stay caught by this same generic rule.
REDACTED_SUFFIXES = ('_email', '_emails')


def _redact_for_admin(details: dict) -> dict:
    return {k: v for k, v in details.items() if not k.endswith(REDACTED_SUFFIXES)}


@router.get("")
def get_ledger(db: Session = Depends(get_db),
               current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR]))):
    entries = db.query(LedgerEntry).order_by(LedgerEntry.index.asc()).all()
    is_auditor = current_user.role == UserRole.AUDITOR
    return [
        {
            "index": e.index, "event_type": e.event_type.value,
            "actor_id": str(e.actor_id) if e.actor_id else None,
            "exam_event_id": str(e.exam_event_id) if e.exam_event_id else None,
            "details": e.details_json if is_auditor else _redact_for_admin(e.details_json),
            "timestamp": e.timestamp.timestamp(),
            "prev_hash": e.prev_hash, "entry_hash": e.entry_hash,
        }
        for e in entries
    ]


@router.get("/verify")
def verify_ledger(db: Session = Depends(get_db),
                   current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR]))):
    return ledger_service.verify_chain(db)