"""
Real encryption at rest for each custodian's per-variant Shamir share
value (CustodianVariantShare.share_y_encrypted) — closes a previously
documented known gap where this field just stored the plain integer as
a string, not actually encrypted (its name was aspirational until now,
same class of gap as the item-bank content issue that was already
fixed in item_bank_service.py).

Uses a SEPARATE system-wide key from both the item-bank key and from
any individual variant's own AES key — this key exists only to protect
share values at rest in the database; it has nothing to do with
reconstructing the paper itself (that's what the shares decrypt to
reveal, via Shamir reconstruction — a completely different operation).

Threat model this protects against: a database-only compromise (a
stolen backup, a read-only SQL injection, a curious DBA with direct DB
access) can no longer read raw share values. It does NOT protect
against a fully compromised application server, since the server needs
this key to do its job — same accepted threat model item_bank_service's
encryption already operates under. A stronger design — per-custodian,
credential-derived keys — would close that remaining gap too, at the
cost of breaking the one-click auto-fetch UX (the server couldn't
decrypt without the custodian's password at that exact moment). That's
real future work, not something to fake here.
"""
import json

from app.config import settings
from app.core import paper_crypto

_CUSTODIAN_SHARE_KEY = bytes.fromhex(settings.custodian_share_encryption_key)


def encrypt_share_value(y: int) -> str:
    """Called once, at compile time, right after Shamir splitting produces y."""
    encrypted = paper_crypto.encrypt_paper(str(y).encode(), _CUSTODIAN_SHARE_KEY)
    return json.dumps({"nonce": encrypted["nonce"], "ciphertext": encrypted["ciphertext"]})


def decrypt_share_value(stored_value: str) -> int:
    """
    Called ONLY at the two legitimate points that need the real y value:
    reconstruction during unlock (custodian_service._get_submitted_shares),
    and a custodian fetching their own share (candidates.py's my_share —
    actually custodians.py's my_share endpoint). Never call this to
    return a value to anyone other than the owning custodian or the
    reconstruction process itself.
    """
    bundle = json.loads(stored_value)
    plaintext_bytes = paper_crypto.decrypt_paper(
        {"nonce": bundle["nonce"], "ciphertext": bundle["ciphertext"], "associated_data": None},
        _CUSTODIAN_SHARE_KEY,
    )
    return int(plaintext_bytes.decode())