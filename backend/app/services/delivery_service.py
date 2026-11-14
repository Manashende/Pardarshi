"""
CBT delivery — turns the reconstructed plaintext paper into a redacted,
student-safe form and persists it once, at the moment of successful CBT
unlock. This is the ONLY place correct_option_indices is ever allowed
to be dropped rather than passed along — every other place in the
system either keeps it encrypted or never touches it at all.
"""
import json
from typing import List, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.delivered_paper import DeliveredPaper


def redact_paper_text(paper_text: bytes) -> List[Dict]:
    """
    paper_text is the raw plaintext bytes returned by
    custodian_service.attempt_unlock() — see item_bank_service's
    assemble_variant_plaintext for the exact shape being parsed here:
    {"questions": [{"question_id": ..., "content": "<json string>", "tags": [...]}]}
    where `content` is itself a JSON string of
    {"question_type", "question_text", "options", "correct_option_indices"}.

    Defensive by design: a single malformed question (e.g. old item bank
    rows submitted before the structured question_type/options schema
    existed — often raw test strings typed straight into Swagger) must
    NEVER be able to crash delivery for an entire exam, for every
    student. Any question that doesn't parse into the expected shape is
    skipped and logged, not fatal.
    """
    assembled = json.loads(paper_text.decode())
    redacted_questions = []
    for q in assembled["questions"]:
        try:
            content = json.loads(q["content"])
            redacted_questions.append({
                "question_id": q["question_id"],
                "question_type": content["question_type"],
                "question_text": content["question_text"],
                "options": content["options"],
                # correct_option_indices deliberately omitted — this is
                # the entire point of this function.
                "tags": q.get("tags", []),
            })
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(
                f"WARNING: skipping malformed question {q.get('question_id', '?')} "
                f"during delivery redaction — likely pre-dates the structured "
                f"question schema: {e}"
            )
    return redacted_questions


def deliver_to_candidates(db: Session, variant_id: UUID, paper_text: bytes) -> DeliveredPaper:
    """
    Idempotent: if this variant was already delivered (e.g. a second
    unlock attempt after the first already succeeded), returns the
    existing row rather than creating a duplicate or re-deriving content.
    """
    existing = db.query(DeliveredPaper).filter(DeliveredPaper.variant_id == variant_id).first()
    if existing is not None:
        return existing

    redacted = redact_paper_text(paper_text)
    delivered = DeliveredPaper(variant_id=variant_id, questions_json=redacted)
    db.add(delivered)
    db.flush()
    return delivered