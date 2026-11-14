"""
Module 7 — simulated parallelized decrypt-and-print dispatch.

CBSE's own CPPT pilot took ~90 minutes to print 450 papers on
effectively a single-printer bottleneck. This splits total_copies
across num_printers simulated printers so elapsed time scales down
roughly linearly with printer count.
"""
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.print_job import PrintJob

# Calibrated against CBSE's own reported figure (450 papers, single
# printer, ~90 minutes) rather than an assumed raw print speed —
# 450/90 = 5 papers/minute. This reflects the FULL per-paper overhead
# (decrypt, print, collate, security handling), not just page-feed
# speed. Cite this reasoning in your report rather than presenting the
# rate as a bare constant.
PAGES_PER_MINUTE_PER_PRINTER = 5


def dispatch_print_jobs(db: Session, variant_id: UUID, centre_id: UUID,
                         total_copies: int, num_printers: int) -> List[PrintJob]:
    if num_printers < 1:
        raise ValueError("num_printers must be at least 1")

    base_copies = total_copies // num_printers
    remainder = total_copies % num_printers

    jobs = []
    now = datetime.now(timezone.utc)
    for printer_id in range(1, num_printers + 1):
        copies = base_copies + (1 if printer_id <= remainder else 0)
        if copies == 0:
            continue
        elapsed_seconds = (copies / PAGES_PER_MINUTE_PER_PRINTER) * 60
        completed_at = datetime.fromtimestamp(now.timestamp() + elapsed_seconds, tz=timezone.utc)

        job = PrintJob(
            variant_id=variant_id, centre_id=centre_id,
            simulated_printer_id=printer_id, copies_assigned=copies,
            started_at=now, completed_at=completed_at,
        )
        db.add(job)
        jobs.append(job)

    db.flush()
    return jobs


def compute_makespan_seconds(jobs: List[PrintJob]) -> float:
    """Bounded by the SLOWEST printer — that's what parallelization buys you."""
    if not jobs:
        return 0.0
    return max((j.completed_at - j.started_at).total_seconds() for j in jobs)