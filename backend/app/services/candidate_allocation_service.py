"""
Automated candidate-to-centre allocation, modeled on how JEE Main /
MHT-CET actually allocate exam centres: students submit ranked
preferences, an automated pass assigns each to the first preferred
centre with remaining capacity, processed in application order
(first-come-first-served, same as the real systems).

Where this improves on the real thing: every allocation decision is
logged to the tamper-evident ledger with its actual reasoning (which
preference rank was granted, or that a geodesic-nearest fallback was
used) — real NTA/CET allocation is an opaque black box with no
visibility into why a candidate got the centre they got. The fallback
itself is also smarter: nearest centre WITH REMAINING CAPACITY to the
candidate's declared location, rather than an arbitrary reassignment.
"""
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from geopy.distance import geodesic
from sqlalchemy.orm import Session

from app.models.candidate_application import CandidateApplication
from app.models.candidate_assignment import CandidateAssignment
from app.models.exam_centre import ExamCentre
from app.models.ledger_entry import LedgerEventType
from app.services import ledger_service


@dataclass
class AllocationOutcome:
    user_id: str
    centre_id: Optional[str]
    method: str  # "preference" | "nearest_fallback" | "unallocated"
    preference_rank: Optional[int]  # 1-based, only set when method == "preference"


def allocate_candidates(db: Session, exam_event_id: UUID, triggered_by_admin_id: UUID) -> List[AllocationOutcome]:
    """
    Idempotent-safe: candidates already holding a CandidateAssignment for
    this exam event (e.g. from a manual override done before this bulk
    run, or from a previous allocation pass) are skipped entirely — this
    can be re-run safely without double-booking a centre or reassigning
    someone who already has a locked allocation.
    """
    applications = (
        db.query(CandidateApplication)
        .filter(CandidateApplication.exam_event_id == exam_event_id)
        .order_by(CandidateApplication.applied_at.asc())
        .all()
    )

    centres = {c.id: c for c in db.query(ExamCentre).all()}

    occupancy = {c.id: 0 for c in centres.values()}
    existing_assignments = (
        db.query(CandidateAssignment)
        .filter(CandidateAssignment.exam_event_id == exam_event_id)
        .all()
    )
    already_assigned_user_ids = set()
    for a in existing_assignments:
        occupancy[a.centre_id] = occupancy.get(a.centre_id, 0) + 1
        already_assigned_user_ids.add(a.user_id)

    outcomes: List[AllocationOutcome] = []

    for application in applications:
        if application.user_id in already_assigned_user_ids:
            continue

        assigned_centre_id = None
        method = "unallocated"
        preference_rank = None

        for rank, centre_id_str in enumerate(application.preferred_centre_ids, start=1):
            centre_id = UUID(centre_id_str)
            centre = centres.get(centre_id)
            if centre is None:
                continue
            if occupancy.get(centre_id, 0) < centre.expected_candidate_count:
                assigned_centre_id = centre_id
                method = "preference"
                preference_rank = rank
                break

        if (assigned_centre_id is None
                and application.declared_latitude is not None
                and application.declared_longitude is not None):
            candidate_point = (application.declared_latitude, application.declared_longitude)
            centres_with_room = [
                c for c in centres.values()
                if occupancy.get(c.id, 0) < c.expected_candidate_count
            ]
            if centres_with_room:
                nearest = min(
                    centres_with_room,
                    key=lambda c: geodesic(candidate_point, (c.latitude, c.longitude)).km,
                )
                assigned_centre_id = nearest.id
                method = "nearest_fallback"

        if assigned_centre_id is not None:
            occupancy[assigned_centre_id] = occupancy.get(assigned_centre_id, 0) + 1
            assignment = CandidateAssignment(
                user_id=application.user_id, exam_event_id=exam_event_id, centre_id=assigned_centre_id,
            )
            db.add(assignment)
            ledger_service.append(
                db, LedgerEventType.CANDIDATE_ALLOCATED,
                details={
                    "candidate_id": str(application.user_id), "centre_id": str(assigned_centre_id),
                    "method": method, "preference_rank": preference_rank,
                },
                actor_id=triggered_by_admin_id, exam_event_id=exam_event_id,
            )

        outcomes.append(AllocationOutcome(
            user_id=str(application.user_id),
            centre_id=str(assigned_centre_id) if assigned_centre_id else None,
            method=method,
            preference_rank=preference_rank,
        ))

    db.commit()
    return outcomes