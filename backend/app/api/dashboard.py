from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.variant_assignment import VariantAssignment
from app.models.print_job import PrintJob
from app.models.access_attempt import AccessAttempt
from app.models.ledger_entry import LedgerEntry, LedgerEventType

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(
    exam_event_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR])),
):
    assignments = db.query(VariantAssignment).filter(VariantAssignment.exam_event_id == exam_event_id).all()
    centres_total = len(assignments)
    variant_ids = [a.variant_id for a in assignments]

    unlocked_variant_ids = {
        e.details_json.get("variant_id")
        for e in db.query(LedgerEntry)
        .filter(LedgerEntry.exam_event_id == exam_event_id, LedgerEntry.event_type == LedgerEventType.VARIANT_DECRYPTED)
        .all()
    }
    centres_unlocked = sum(1 for a in assignments if str(a.variant_id) in unlocked_variant_ids)

    print_jobs = db.query(PrintJob).filter(PrintJob.variant_id.in_(variant_ids)).all() if variant_ids else []
    jobs_by_centre = {}
    for j in print_jobs:
        jobs_by_centre.setdefault(j.centre_id, []).append(j)

    centres_printing = sum(1 for jobs in jobs_by_centre.values() if any(j.completed_at is None for j in jobs))
    centres_print_complete = sum(1 for jobs in jobs_by_centre.values() if all(j.completed_at is not None for j in jobs))

    flagged = (
        db.query(AccessAttempt)
        .filter(AccessAttempt.overall_passed == False)  # noqa: E712
        .order_by(AccessAttempt.timestamp.desc())
        .limit(10)
        .all()
    )

    return {
        "exam_event_id": str(exam_event_id),
        "centres_total": centres_total,
        "centres_unlocked": centres_unlocked,
        "centres_printing": centres_printing,
        "centres_print_complete": centres_print_complete,
        "flagged_access_attempts": db.query(AccessAttempt).filter(AccessAttempt.overall_passed == False).count(),  # noqa: E712
        "recent_flagged": [
            {
                "user_id": str(a.user_id), "action": a.action,
                "role_check_passed": a.role_check_passed, "device_check_passed": a.device_check_passed,
                "location_check_passed": a.location_check_passed, "time_window_check_passed": a.time_window_check_passed,
                "timestamp": a.timestamp.timestamp(),
            }
            for a in flagged
        ],
    }
    
@router.get("/flagged")
def system_flagged_attempts(
    limit: int = Query(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.AUDITOR])),
):
    total = db.query(AccessAttempt).filter(AccessAttempt.overall_passed == False).count()  # noqa: E712
    recent = (
        db.query(AccessAttempt)
        .filter(AccessAttempt.overall_passed == False)  # noqa: E712
        .order_by(AccessAttempt.timestamp.desc())
        .limit(limit)
        .all()
    )
    return {
        "total_flagged": total,
        "recent": [
            {"user_id": str(a.user_id), "action": a.action,
             "role_check_passed": a.role_check_passed, "device_check_passed": a.device_check_passed,
             "location_check_passed": a.location_check_passed, "time_window_check_passed": a.time_window_check_passed,
             "timestamp": a.timestamp.timestamp()}
            for a in recent
        ],
    }