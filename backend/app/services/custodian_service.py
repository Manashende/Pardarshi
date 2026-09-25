"""
Modules 3+4 tied together — the real unlock policy, generalized to
per-variant with standard+override paths.
"""
from dataclasses import dataclass
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import shamir, paper_crypto
from app.services import ledger_service, time_verification
from app.models.custodian import Custodian
from app.models.share_submission import ShareSubmission, SubmissionType
from app.models.paper_variant import PaperVariant
from app.models.exam_event import ExamEvent
from app.models.ledger_entry import LedgerEventType
from app.models.custodian_variant_share import CustodianVariantShare


@dataclass
class UnlockResult:
    status: str
    reason: Optional[str]
    paper_text: Optional[bytes]


def submit_share(db: Session, variant_id: UUID, custodian_id: UUID,
                  submission_type: SubmissionType, ntp_verified_time: float) -> ShareSubmission:
    submission = ShareSubmission(
        variant_id=variant_id, custodian_id=custodian_id,
        submission_type=submission_type, ntp_verified_time=ntp_verified_time,
    )
    db.add(submission)
    db.flush()

    custodian = db.query(Custodian).filter(Custodian.id == custodian_id).first()
    ledger_service.append(
        db, LedgerEventType.SHARE_SUBMITTED,
        details={"variant_id": str(variant_id), "custodian_id": str(custodian_id),
                  "submission_type": submission_type.value},
        actor_id=custodian.user_id if custodian else None,
    )
    return submission


def _get_submitted_shares(db: Session, variant_id: UUID, submission_type: SubmissionType) -> List[Tuple[int, int]]:
    submissions = (
        db.query(ShareSubmission)
        .filter(ShareSubmission.variant_id == variant_id, ShareSubmission.submission_type == submission_type)
        .all()
    )
    seen_custodians = set()
    shares = []
    for sub in submissions:
        if sub.custodian_id in seen_custodians:
            continue
        seen_custodians.add(sub.custodian_id)
        custodian = db.query(Custodian).filter(Custodian.id == sub.custodian_id).first()
        if custodian is None:
            continue
        variant_share = (
            db.query(CustodianVariantShare)
            .filter(CustodianVariantShare.custodian_id == custodian.id, CustodianVariantShare.variant_id == variant_id)
            .first()
        )
        if variant_share is None:
            continue
        y = int(variant_share.share_y_encrypted)
        shares.append((custodian.share_x, y))
    return shares


def attempt_unlock(db: Session, variant_id: UUID, ntp_servers: List[str],
                    centre_id: Optional[UUID] = None) -> UnlockResult:
    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    if variant is None:
        return UnlockResult(status="denied", reason="variant not found", paper_text=None)

    exam_event = db.query(ExamEvent).filter(ExamEvent.id == variant.exam_event_id).first()

    verified_time = time_verification.get_verified_time(ntp_servers)
    is_standard_time_ok = (
        time_verification.is_acceptable_for_standard_unlock(verified_time.verification_level)
        and verified_time.epoch >= exam_event.exam_start_epoch
    )

    if not is_standard_time_ok:
        if verified_time.epoch < exam_event.exam_start_epoch:
            reason = f"exam has not started yet ({exam_event.exam_start_epoch - verified_time.epoch:.0f}s remaining)"
        else:
            reason = f"time verification insufficient for standard unlock (level={verified_time.verification_level.value})"
        ledger_service.append(db, LedgerEventType.UNLOCK_DENIED_TIME, details={
            "variant_id": str(variant_id), "reason": reason,
            "verification_level": verified_time.verification_level.value,
        }, exam_event_id=exam_event.id)
        db.commit()
        return UnlockResult(status="denied", reason=reason, paper_text=None)

    standard_shares = _get_submitted_shares(db, variant_id, SubmissionType.STANDARD)
    if len(standard_shares) >= exam_event.threshold:
        return _do_reconstruction(db, variant, exam_event, standard_shares, centre_id)

    if verified_time.epoch > exam_event.override_window_end_epoch:
        override_shares = _get_submitted_shares(db, variant_id, SubmissionType.OVERRIDE)
        if len(override_shares) >= exam_event.override_threshold:
            return _do_reconstruction(db, variant, exam_event, override_shares, centre_id)
        reason = f"override path: only {len(override_shares)}/{exam_event.override_threshold} shares submitted"
    else:
        reason = f"only {len(standard_shares)}/{exam_event.threshold} shares submitted"

    ledger_service.append(db, LedgerEventType.UNLOCK_DENIED_THRESHOLD, details={
        "variant_id": str(variant_id), "reason": reason,
    }, exam_event_id=exam_event.id)
    db.commit()
    return UnlockResult(status="denied", reason=reason, paper_text=None)


def _do_reconstruction(db: Session, variant: PaperVariant, exam_event: ExamEvent,
                        shares: List[Tuple[int, int]], centre_id: Optional[UUID]) -> UnlockResult:
    secret_int = shamir.reconstruct_secret(shares)
    key = shamir.int_to_bytes(secret_int, 32)

    encrypted = {"nonce": variant.nonce, "ciphertext": variant.ciphertext, "associated_data": None}
    try:
        plaintext = paper_crypto.decrypt_paper(encrypted, key)
    except Exception:
        ledger_service.append(db, LedgerEventType.UNLOCK_DENIED_THRESHOLD, details={
            "variant_id": str(variant.id), "reason": "decryption failed after reconstruction — possible corrupted shares",
        }, exam_event_id=exam_event.id)
        db.commit()
        return UnlockResult(status="denied", reason="decryption failed — corrupted or invalid shares", paper_text=None)

    ledger_service.append(db, LedgerEventType.VARIANT_DECRYPTED, details={
        "variant_id": str(variant.id), "centre_id": str(centre_id) if centre_id else None,
        "shares_used": len(shares),
    }, exam_event_id=exam_event.id)
    db.commit()
    return UnlockResult(status="unlocked", reason=None, paper_text=plaintext)