"""AES-256-GCM encryption for question paper variants."""
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def encrypt_paper(plaintext: bytes, key: bytes, associated_data: bytes = None) -> dict:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    return {
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
        "associated_data": associated_data.hex() if associated_data else None,
    }


def decrypt_paper(encrypted: dict, key: bytes) -> bytes:
    aesgcm = AESGCM(key)
    nonce = bytes.fromhex(encrypted["nonce"])
    ciphertext = bytes.fromhex(encrypted["ciphertext"])
    ad = bytes.fromhex(encrypted["associated_data"]) if encrypted.get("associated_data") else None
    return aesgcm.decrypt(nonce, ciphertext, ad)