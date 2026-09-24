import app.models  # noqa: F401
from app.core import shamir, paper_crypto
from app.services import variant_assignment

key = paper_crypto.generate_key()
secret_int = shamir.bytes_to_int(key)
shares = shamir.split_secret(secret_int, n=5, t=3)
recovered = shamir.int_to_bytes(shamir.reconstruct_secret(shares[:3]), 32)
assert recovered == key
print("Shamir: OK")

enc = paper_crypto.encrypt_paper(b"test paper", key, associated_data=b"centre=X")
dec = paper_crypto.decrypt_paper(enc, key)
assert dec == b"test paper"
print("AES-GCM: OK")

secret = variant_assignment.generate_assignment_secret()
a1 = variant_assignment.compute_assignment(secret, "PUNE-042", "2027-01-15", num_variants=5)
print("Variant assignment:", a1)
assert variant_assignment.verify_assignment(secret, "PUNE-042", "2027-01-15", 5, a1["assignment_hash"])
print("Verification: OK")