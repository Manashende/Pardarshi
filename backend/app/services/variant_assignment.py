"""
Module 6 / Algorithm E — deterministic-but-unpredictable variant
assignment, for blast-radius reduction.

assignment_hash = HMAC(assignment_secret, centre_id || exam_date)
variant_index = assignment_hash (as int) mod num_variants

- Deterministic: same (secret, centre_id, exam_date) always gives the
  same assignment, so an auditor holding the secret can recompute and
  verify it later.
- Unpredictable without the secret: HMAC-SHA256 is a PRF — without the
  key, output is indistinguishable from random.
- Only assignment_secret_hash (a hash of the secret) is ever stored in
  the DB — the actual secret is held only in memory / at compile-time
  by ADMIN, exactly like the SSS master key is never stored whole.
"""
import hashlib
import hmac
import secrets


def generate_assignment_secret() -> bytes:
    return secrets.token_bytes(32)


def hash_secret_for_storage(secret: bytes) -> str:
    return hashlib.sha256(secret).hexdigest()


def compute_assignment(secret: bytes, centre_id: str, exam_date: str, num_variants: int) -> dict:
    """exam_date should be a stable string like '2027-01-15', not a full timestamp."""
    message = f"{centre_id}|{exam_date}".encode()
    digest = hmac.new(secret, message, hashlib.sha256).digest()
    assignment_hash = digest.hex()
    variant_index = int.from_bytes(digest, byteorder="big") % num_variants
    return {"assignment_hash": assignment_hash, "variant_index": variant_index}


def verify_assignment(secret: bytes, centre_id: str, exam_date: str,
                       num_variants: int, claimed_assignment_hash: str) -> bool:
    """What an AUDITOR does after the fact to verify an assignment wasn't tampered with."""
    recomputed = compute_assignment(secret, centre_id, exam_date, num_variants)
    return hmac.compare_digest(recomputed["assignment_hash"], claimed_assignment_hash)