from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.print_job import PrintJob

router = APIRouter(prefix="/print-jobs", tags=["print-jobs"])


@router.get("/{print_job_id}/status")
def print_job_status(print_job_id: UUID, db: Session = Depends(get_db),
                      current_user: User = Depends(require_role(list(UserRole)))):
    job = db.query(PrintJob).filter(PrintJob.id == print_job_id).first()
    if job is None:
        raise HTTPException(404, "print job not found")

    elapsed = (job.completed_at - job.started_at).total_seconds() if job.completed_at else None

    return {
        "print_job_id": str(job.id), "centre_id": str(job.centre_id),
        "simulated_printer_id": job.simulated_printer_id, "copies_assigned": job.copies_assigned,
        "started_at": job.started_at.timestamp(),
        "completed_at": job.completed_at.timestamp() if job.completed_at else None,
        "elapsed_seconds": elapsed,
    }


@router.get("/by-variant/{variant_id}/summary")
def print_jobs_summary_for_variant(variant_id: UUID, db: Session = Depends(get_db),
                                    current_user: User = Depends(require_role(list(UserRole)))):
    """
    Not in the original OpenAPI spec — added because a single unlock
    creates several print jobs (one per simulated printer), and the
    dashboard needs the aggregate (makespan = slowest printer, not the
    sum) more often than any single job's status.
    """
    jobs = db.query(PrintJob).filter(PrintJob.variant_id == variant_id).all()
    if not jobs:
        return {"variant_id": str(variant_id), "jobs": [], "total_copies": 0, "makespan_seconds": None}

    total_copies = sum(j.copies_assigned for j in jobs)
    makespan = max((j.completed_at - j.started_at).total_seconds() for j in jobs if j.completed_at)

    return {
        "variant_id": str(variant_id), "num_printers_used": len(jobs),
        "total_copies": total_copies, "makespan_seconds": makespan,
        "jobs": [
            {"printer_id": j.simulated_printer_id, "copies": j.copies_assigned,
             "elapsed_seconds": (j.completed_at - j.started_at).total_seconds() if j.completed_at else None,
             "completed_at": j.completed_at.timestamp() if j.completed_at else None}
            for j in jobs
        ],
    }