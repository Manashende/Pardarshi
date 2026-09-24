"""
Module 1 — the distributed question item bank and automated assembly.

Two responsibilities, kept together since they're tightly coupled:

1. Real encryption at rest for submitted questions (fixing a gap where
   `encrypted_content` was previously just storing whatever string was
   sent, not actually encrypted). Uses a system-wide item-bank key —
   this is DIFFERENT from any single variant's AES key; it exists only
   so the assembly step below can decrypt questions in memory, briefly,
   never returning plaintext to any API response or client.

2. Automated selection + assembly: given a target number of variants
   and questions-per-variant, pulls that many questions per variant
   from the bank, decrypts them server-side (in memory only), and
   concatenates them into one assembled plaintext per variant — with
   no human, including the admin triggering compile, ever seeing the
   result. That plaintext is what compile_service.compile_variant()
   then encrypts with a fresh per-variant key and splits via Shamir.
"""
import json
import random
from typing import List

from sqlalchemy.orm import Session

from app.config import settings
from app.core import paper_crypto
from app.models.question import Question

_ITEM_BANK_KEY = bytes.fromhex(settings.item_bank_encryption_key)


def encrypt_question_content(plaintext_content: str) -> str:
    """
    Called once, at submission time. Returns a JSON string bundling the
    nonce + ciphertext together, so no schema migration is needed to
    store them separately — this whole bundle is what actually gets
    saved into Question.encrypted_content.
    """
    encrypted = paper_crypto.encrypt_paper(plaintext_content.encode(), _ITEM_BANK_KEY)
    return json.dumps({"nonce": encrypted["nonce"], "ciphertext": encrypted["ciphertext"]})


def decrypt_question_content(stored_value: str) -> str:
    """
    The inverse — used ONLY by the assembly step below, server-side,
    in memory. Never call this to return content to any API response.
    """
    bundle = json.loads(stored_value)
    plaintext_bytes = paper_crypto.decrypt_paper(
        {"nonce": bundle["nonce"], "ciphertext": bundle["ciphertext"], "associated_data": None},
        _ITEM_BANK_KEY,
    )
    return plaintext_bytes.decode()


class InsufficientQuestionsError(Exception):
    pass


def select_questions_for_variants(
    db: Session, num_variants: int, questions_per_variant: int
) -> List[List[Question]]:
    """
    Returns a list of length num_variants, each element a list of
    `questions_per_variant` distinct Question rows for that variant.

    Policy: NO duplicate questions within a single variant's paper
    (that would be a broken exam paper). Across DIFFERENT variants,
    reuse is allowed if the bank is too small to give every variant a
    fully distinct set — this is a documented, deliberate degradation
    for small item banks (e.g. during testing), not silently pretended
    away. A real deployment would want a much larger bank relative to
    num_variants * questions_per_variant so overlap is rare in practice.
    """
    all_questions = db.query(Question).all()
    if len(all_questions) < questions_per_variant:
        raise InsufficientQuestionsError(
            f"Item bank has {len(all_questions)} questions, need at least "
            f"{questions_per_variant} per variant."
        )

    variants_selection = []
    for _ in range(num_variants):
        # Sample without replacement WITHIN this variant (no dupes in
        # one paper); across variants, we resample independently, which
        # means overlap is possible if the bank is small.
        selected = random.sample(all_questions, questions_per_variant)
        variants_selection.append(selected)
    return variants_selection


def assemble_variant_plaintext(selected_questions: List[Question]) -> bytes:
    """
    Decrypts each selected question server-side (in memory only) and
    assembles them into one paper. This is the point where "no human
    views the assembled result" is actually enforced — this function
    runs inside the compile request handler and its return value is
    immediately re-encrypted by compile_service; it is never returned
    to any API response or logged anywhere.
    """
    assembled = []
    for q in selected_questions:
        content = decrypt_question_content(q.encrypted_content)
        assembled.append({"question_id": str(q.id), "content": content, "tags": q.tags})
    return json.dumps({"questions": assembled}).encode()