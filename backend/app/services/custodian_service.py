"""
Modules 3+4 tied together — the real unlock policy, generalized to
per-variant with standard+override paths.

PRINT vs CBT timing (added alongside the delivery_mode split):
- CBT: unchanged, strict — reconstruction only allowed once verified
  time has reached exam_start_epoch. No early access under any
  circumstance; a digital paper is too easy to silently copy or leak
  once decrypted, so there's no substitute trust mechanism offered.
- PRINT: reconstruction may begin as early as
  (exam_start_epoch - print_window_hours * 3600), but ONLY once at
  least required_officials_count distinct on-site officials have
  confirmed physical presence for that (exam_event, centre) pair (see
  app/api/officials.py). This substitutes named, identified human
  accountability for exact-second timing precision — a deliberate,
  documented trade-off, not a relaxation of security.
"""
from dataclasses import dataclass
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import shamir, paper_crypto, share_crypto
from app.services import ledger_service, time_verification
from app.models.user import User
from app.models.custodian import Custodian
from app.models.share_submission import ShareSubmission, SubmissionType
from app.models.paper_variant import PaperVariant
from app.models.exam_event import ExamEvent, DeliveryMode
from app.models.exam_centre import ExamCentre
from app.models.ledger_entry import LedgerEventType
from app.models.custodian_variant_share import CustodianVariantShare
from app.models.official_presence_confirmation import OfficialPresenceConfirmation


@dataclass
class UnlockResult:
    status: str
    reason: Optional[str]
    paper_text: Optional[bytes]


class ShareMismatchError(Exception):
    """
    Raised when a custodian's submitted (x, y) doesn't match what the
    server actually has on record for them on this variant. This is
    what turns a share submission into real proof-of-possession —
    previously nothing about the submitted value was checked before it
    counted toward the threshold; any authenticated custodian could
    submit garbage and it would count the same as a genuine share.
    """


def submit_share(db: Session, variant_id: UUID, custodian_id: UUID,
                  submission_type: SubmissionType, ntp_verified_time: float,
                  claimed_x: int, claimed_y: str) -> ShareSubmission:
    custodian = db.query(Custodian).filter(Custodian.id == custodian_id).first()
    if custodian is None:
        raise ShareMismatchError("custodian not found")

    # Fetched once, reused for both the failure and success ledger entries
    # below — human-readable context captured at write-time, per
    # ledger_service.py's design note on why an audit log must freeze
    # names now rather than resolve them via a later lookup.
    custodian_user = db.query(User).filter(User.id == custodian.user_id).first()
    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    exam_event = db.query(ExamEvent).filter(ExamEvent.id == variant.exam_event_id).first() if variant else None

    variant_share = (
        db.query(CustodianVariantShare)
        .filter(CustodianVariantShare.custodian_id == custodian_id, CustodianVariantShare.variant_id == variant_id)
        .first()
    )
    if variant_share is None:
        raise ShareMismatchError("no share has been generated for you on this variant yet")

    real_y = share_crypto.decrypt_share_value(variant_share.share_y_encrypted)

    if claimed_x != custodian.share_x or str(claimed_y) != str(real_y):
        ledger_service.append(
            db, LedgerEventType.SHARE_VERIFICATION_FAILED,
            details={
                "variant_id": str(variant_id),
                "exam_event_name": exam_event.exam_name if exam_event else None,
                "custodian_id": str(custodian_id),
                "custodian_email": custodian_user.email if custodian_user else None,
            },
            actor_id=custodian.user_id,
        )
        db.commit()
        raise ShareMismatchError(
            "submitted share does not match the server's record for this custodian — "
            "submission rejected, not counted toward the threshold"
        )

    submission = ShareSubmission(
        variant_id=variant_id, custodian_id=custodian_id,
        submission_type=submission_type, ntp_verified_time=ntp_verified_time,
    )
    db.add(submission)
    db.flush()

    ledger_service.append(
        db, LedgerEventType.SHARE_SUBMITTED,
        details={
            "variant_id": str(variant_id),
            "exam_event_name": exam_event.exam_name if exam_event else None,
            "custodian_id": str(custodian_id),
            "custodian_email": custodian_user.email if custodian_user else None,
            "submission_type": submission_type.value,
        },
        actor_id=custodian.user_id,
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
        y = share_crypto.decrypt_share_value(variant_share.share_y_encrypted)
        shares.append((custodian.share_x, y))
    return shares


def _earliest_reconstruction_epoch(exam_event: ExamEvent) -> float:
    if exam_event.delivery_mode == DeliveryMode.PRINT:
        return exam_event.exam_start_epoch - (exam_event.print_window_hours * 3600)
    return exam_event.exam_start_epoch


def _officials_satisfied(db: Session, exam_event: ExamEvent, centre_id: Optional[UUID]) -> Tuple[bool, int]:
    """Only meaningful for PRINT mode — CBT always passes this check."""
    if exam_event.delivery_mode != DeliveryMode.PRINT:
        return True, 0
    if centre_id is None:
        # No centre context (shouldn't happen via the real unlock endpoint,
        # which always supplies one) — fail closed rather than silently pass.
        return False, 0
    confirmed_count = (
        db.query(OfficialPresenceConfirmation)
        .filter(OfficialPresenceConfirmation.exam_event_id == exam_event.id,
                OfficialPresenceConfirmation.centre_id == centre_id)
        .count()
    )
    return confirmed_count >= exam_event.required_officials_count, confirmed_count


def attempt_unlock(db: Session, variant_id: UUID, ntp_servers: List[str],
                    centre_id: Optional[UUID] = None) -> UnlockResult:
    variant = db.query(PaperVariant).filter(PaperVariant.id == variant_id).first()
    if variant is None:
        return UnlockResult(status="denied", reason="variant not found", paper_text=None)

    exam_event = db.query(ExamEvent).filter(ExamEvent.id == variant.exam_event_id).first()

    verified_time = time_verification.get_verified_time(ntp_servers)
    earliest_epoch = _earliest_reconstruction_epoch(exam_event)
    is_standard_time_ok = (
        time_verification.is_acceptable_for_standard_unlock(verified_time.verification_level)
        and verified_time.epoch >= earliest_epoch
    )

    if not is_standard_time_ok:
        if verified_time.epoch < earliest_epoch:
            reason = f"not yet within the release window ({earliest_epoch - verified_time.epoch:.0f}s remaining)"
        else:
            reason = f"time verification insufficient for standard unlock (level={verified_time.verification_level.value})"
        ledger_service.append(db, LedgerEventType.UNLOCK_DENIED_TIME, details={
            "variant_id": str(variant_id), "exam_event_name": exam_event.exam_name, "reason": reason,
            "verification_level": verified_time.verification_level.value,
        }, exam_event_id=exam_event.id)
        db.commit()
        return UnlockResult(status="denied", reason=reason, paper_text=None)

    officials_ok, officials_confirmed = _officials_satisfied(db, exam_event, centre_id)
    if not officials_ok:
        reason = (
            f"PRINT mode requires {exam_event.required_officials_count} on-site officials "
            f"confirmed present, only {officials_confirmed} so far"
        )
        ledger_service.append(db, LedgerEventType.UNLOCK_DENIED_THRESHOLD, details={
            "variant_id": str(variant_id), "exam_event_name": exam_event.exam_name, "reason": reason,
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
        "variant_id": str(variant_id), "exam_event_name": exam_event.exam_name, "reason": reason,
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
            "variant_id": str(variant.id), "exam_event_name": exam_event.exam_name,
            "reason": "decryption failed after reconstruction — possible corrupted shares",
        }, exam_event_id=exam_event.id)
        db.commit()
        return UnlockResult(status="denied", reason="decryption failed — corrupted or invalid shares", paper_text=None)

    centre = db.query(ExamCentre).filter(ExamCentre.id == centre_id).first() if centre_id else None
    ledger_service.append(db, LedgerEventType.VARIANT_DECRYPTED, details={
        "variant_id": str(variant.id), "exam_event_name": exam_event.exam_name,
        "centre_id": str(centre_id) if centre_id else None,
        "centre_code": centre.centre_code if centre else None,
        "shares_used": len(shares),
    }, exam_event_id=exam_event.id)
    db.commit()
    return UnlockResult(status="unlocked", reason=None, paper_text=plaintext)