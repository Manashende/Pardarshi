"""
Ties together AES encryption + Shamir splitting + persisting a
PaperVariant, its per-variant custodian shares, and (once per exam
event) the Custodian identity rows.

Two separate operations, since they have different lifetimes:
- get_or_create_custodians(): runs ONCE per exam event, regardless of
  how many variants it has. Creates the (user, exam_event, type, x)
  identity rows if they don't already exist yet; returns them
  otherwise. Safe to call once per variant in a loop — idempotent.
- compile_variant(): runs ONCE PER VARIANT. Generates that variant's
  own fresh AES key, splits it into shares AT THE SAME x-coordinates
  as the existing custodians (so the same 5 people serve every variant
  of one exam, each with a different y per variant), and stores those
  y-values in CustodianVariantShare.
"""
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import shamir, paper_crypto
from app.models.paper_variant import PaperVariant
from app.models.custodian import Custodian, CustodianType
from app.models.custodian_variant_share import CustodianVariantShare


def get_or_create_custodians(
    db: Session,
    exam_event_id: UUID,
    custodian_user_ids: List[UUID],
    custodian_types: List[CustodianType],
) -> List[Custodian]:
    """
    Idempotent: if Custodian rows already exist for this exam event
    (from an earlier variant's compile call), returns those unchanged.
    Otherwise creates one row per (user_id, type) pair, in the given
    order, with share_x = 1, 2, 3, ... matching that order.
    """
    existing = (
        db.query(Custodian)
        .filter(Custodian.exam_event_id == exam_event_id)
        .order_by(Custodian.share_x)
        .all()
    )
    if existing:
        return existing

    assert len(custodian_user_ids) == len(custodian_types), "one type per custodian"

    custodians = []
    for x, (user_id, ctype) in enumerate(zip(custodian_user_ids, custodian_types), start=1):
        custodian = Custodian(
            user_id=user_id, exam_event_id=exam_event_id,
            custodian_type=ctype, share_x=x,
        )
        db.add(custodian)
        custodians.append(custodian)
    db.flush()
    return custodians


def compile_variant(
    db: Session,
    exam_event_id: UUID,
    variant_index: int,
    plaintext: bytes,
    custodians: List[Custodian],
    threshold: int,
    question_ids: List[UUID] = None,
) -> PaperVariant:
    """
    Encrypts `plaintext` with a fresh AES-256 key for THIS variant,
    splits that key via Shamir at the SAME x-coordinates as the given
    (already-existing) custodians, and stores one CustodianVariantShare
    row per custodian for this variant.
    """
    key = paper_crypto.generate_key()
    encrypted = paper_crypto.encrypt_paper(plaintext, key)

    variant = PaperVariant(
        exam_event_id=exam_event_id,
        variant_index=variant_index,
        ciphertext=encrypted["ciphertext"],
        nonce=encrypted["nonce"],
        question_ids=[str(qid) for qid in question_ids] if question_ids else [],
    )
    db.add(variant)
    db.flush()

    secret_int = shamir.bytes_to_int(key)
    n = len(custodians)
    shares = shamir.split_secret(secret_int, n=n, t=threshold)  # [(1, y1), (2, y2), ...]

    # shares[i] is (x=i+1, y) by construction — map it onto the
    # custodian whose fixed share_x matches that same i+1, so every
    # variant's shares line up with the same custodian's identity.
    custodians_by_x = {c.share_x: c for c in custodians}
    for x, y in shares:
        custodian = custodians_by_x[x]
        db.add(CustodianVariantShare(custodian_id=custodian.id, variant_id=variant.id, share_y_encrypted=str(y)))
    db.flush()

    return variant