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

Selection is TAG-AWARE (closes a previously-documented known gap) and
supports two modes:

  1. subject_distribution given (e.g. {"Physics": 25, "Chemistry": 25,
     "Maths": 25} — matches real exam patterns like JEE Main/MHT-CET,
     where subject counts are a FIXED, identical part of the pattern on
     every paper). Subject is the PRIMARY blueprint axis; difficulty
     distribution is applied WITHIN each subject's slice.

  2. subject_distribution not given — falls back to difficulty-primary,
     topic-diversified-secondary selection (draws proportionally across
     difficulty levels, round-robining across distinct topics within
     each level so a variant isn't accidentally dominated by one topic).

In both modes: no duplicate questions within one variant's paper, and
cross-variant reuse is a genuine LAST RESORT — distinctness ACROSS
variants is actively preferred whenever the bank has enough supply, only
falling back to reuse when it genuinely doesn't (a documented, deliberate
degradation for small item banks, not a silent accident).
"""
import json
import random
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.core import paper_crypto
from app.models.question import Question, QuestionDifficulty

_ITEM_BANK_KEY = bytes.fromhex(settings.item_bank_encryption_key)

# Admin can override this per-compile (see exam_events.py's CompileRequest);
# this is just the sensible default when they don't.
DEFAULT_DIFFICULTY_DISTRIBUTION: Dict[QuestionDifficulty, float] = {
    QuestionDifficulty.EASY: 0.3,
    QuestionDifficulty.MEDIUM: 0.5,
    QuestionDifficulty.HARD: 0.2,
}


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


def _normalize_topic(topic: str) -> str:
    """
    New submissions can no longer create inconsistent topic spelling —
    Contributor topic entry is now constrained to an Admin-managed,
    approved list (see app/models/topic.py, app/api/topics.py,
    QuestionForm.jsx), validated server-side in
    app/api/questions.py:submit_question. This function's remaining job
    is narrower: (a) a defensive case/whitespace normalizer so an
    admin's subject_distribution key (e.g. "physics") still matches a
    stored topic value ("Physics") without requiring exact casing, and
    (b) a safety net for any rows submitted before this fix existed.
    """
    return topic.strip().lower()


def _allocate_counts_by_difficulty(
    total: int, distribution: Dict[QuestionDifficulty, float]
) -> Dict[QuestionDifficulty, int]:
    """
    Largest-remainder rounding: converts fractional shares (e.g. 30/50/20
    of `total`) into integer counts that sum EXACTLY to `total`, rather
    than naive int() truncation which can under-allocate by a question
    or two.
    """
    raw = {d: total * frac for d, frac in distribution.items()}
    floors = {d: int(v) for d, v in raw.items()}
    remainder = total - sum(floors.values())
    ranked = sorted(raw.items(), key=lambda kv: kv[1] - floors[kv[0]], reverse=True)
    for i in range(remainder):
        d = ranked[i % len(ranked)][0]
        floors[d] += 1
    return floors


def _pick_topic_diverse(candidates: List[Question], count: int, exclude_ids: set) -> List[Question]:
    """
    Groups candidates by topic and round-robins across topics, so
    `count` questions come from as many DISTINCT topics as the pool
    allows, rather than a plain random.sample() that could easily land
    on 5 questions from the same topic by chance. Used only in the
    fallback (no subject_distribution) mode — once subject is a hard
    blueprint constraint, there's no separate "diversify away from it"
    concept at this level.
    """
    by_topic: Dict[str, List[Question]] = {}
    for q in candidates:
        if q.id in exclude_ids:
            continue
        by_topic.setdefault(q.topic, []).append(q)
    for bucket in by_topic.values():
        random.shuffle(bucket)

    topics = list(by_topic.keys())
    random.shuffle(topics)

    picked: List[Question] = []
    idx = 0
    safety_limit = count * len(topics) + 1000 if topics else 0
    steps = 0
    while len(picked) < count and topics and any(by_topic[t] for t in topics) and steps < safety_limit:
        t = topics[idx % len(topics)]
        if by_topic[t]:
            picked.append(by_topic[t].pop())
        idx += 1
        steps += 1
    return picked


def _select_distinctness_preferred(
    pool: List[Question], count: int, exclude_ids: set, used_globally: set
) -> List[Question]:
    """
    Prefers questions never used in ANY variant so far; falls back to
    reuse only when the pool genuinely can't supply enough fresh ones —
    the cross-variant-distinctness-preferred policy applied uniformly
    across this module. Used by the subject_distribution path, where
    subject+difficulty already fixes the "cell" being drawn from, so no
    separate diversity round-robin is needed on top of it.
    """
    fresh = [q for q in pool if q.id not in used_globally and q.id not in exclude_ids]
    random.shuffle(fresh)
    picked = fresh[:count]
    if len(picked) < count:
        remaining_needed = count - len(picked)
        picked_ids = {q.id for q in picked}
        fallback_pool = [q for q in pool if q.id not in picked_ids and q.id not in exclude_ids]
        random.shuffle(fallback_pool)
        picked.extend(fallback_pool[:remaining_needed])
    return picked


def select_questions_for_variants(
    db: Session,
    num_variants: int,
    questions_per_variant: int,
    difficulty_distribution: Optional[Dict[QuestionDifficulty, float]] = None,
    subject_distribution: Optional[Dict[str, int]] = None,
) -> List[List[Question]]:
    """
    Returns a list of length num_variants, each element a list of
    `questions_per_variant` distinct Question rows for that variant.
    See the module docstring for the two selection modes.
    """
    distribution = difficulty_distribution or DEFAULT_DIFFICULTY_DISTRIBUTION
    if abs(sum(distribution.values()) - 1.0) > 1e-6:
        raise ValueError("difficulty_distribution must sum to 1.0")

    all_questions = db.query(Question).all()
    if len(all_questions) < questions_per_variant:
        raise InsufficientQuestionsError(
            f"Item bank has {len(all_questions)} questions, need at least "
            f"{questions_per_variant} per variant."
        )

    used_globally: set = set()
    variants_selection: List[List[Question]] = []

    if subject_distribution is not None:
        if sum(subject_distribution.values()) != questions_per_variant:
            raise ValueError(
                f"subject_distribution counts ({sum(subject_distribution.values())}) must "
                f"sum exactly to questions_per_variant ({questions_per_variant})."
            )

        by_normalized_topic: Dict[str, List[Question]] = {}
        for q in all_questions:
            by_normalized_topic.setdefault(_normalize_topic(q.topic), []).append(q)

        cells: Dict[Tuple[str, QuestionDifficulty], List[Question]] = {}
        cell_counts: Dict[Tuple[str, QuestionDifficulty], int] = {}

        for subject_name, subject_count in subject_distribution.items():
            normalized_subject = _normalize_topic(subject_name)
            subject_pool = by_normalized_topic.get(normalized_subject, [])

            by_difficulty_in_subject: Dict[QuestionDifficulty, List[Question]] = {}
            for q in subject_pool:
                by_difficulty_in_subject.setdefault(q.difficulty, []).append(q)

            counts_within_subject = _allocate_counts_by_difficulty(subject_count, distribution)
            for difficulty, count in counts_within_subject.items():
                pool = by_difficulty_in_subject.get(difficulty, [])
                if len(pool) < count:
                    raise InsufficientQuestionsError(
                        f"Item bank has only {len(pool)} '{difficulty.value}' question(s) "
                        f"tagged with topic '{subject_name}', but {count} are needed per "
                        f"variant under the configured subject/difficulty pattern. Add more "
                        f"matching questions, or check for inconsistent topic spelling "
                        f"(e.g. 'GK' vs 'General Knowledge')."
                    )
                cells[(normalized_subject, difficulty)] = pool
                cell_counts[(normalized_subject, difficulty)] = count

        for _ in range(num_variants):
            selected: List[Question] = []
            for cell_key, count in cell_counts.items():
                pool = cells[cell_key]
                already_in_this_variant = {q.id for q in selected}
                picked = _select_distinctness_preferred(pool, count, already_in_this_variant, used_globally)
                selected.extend(picked)
            used_globally.update(q.id for q in selected)
            variants_selection.append(selected)
        return variants_selection

    # ---- Fallback: difficulty-primary, topic-diversified-secondary ----
    by_difficulty: Dict[QuestionDifficulty, List[Question]] = {}
    for q in all_questions:
        by_difficulty.setdefault(q.difficulty, []).append(q)

    counts_per_difficulty = _allocate_counts_by_difficulty(questions_per_variant, distribution)

    for difficulty, count in counts_per_difficulty.items():
        available = len(by_difficulty.get(difficulty, []))
        if available < count:
            raise InsufficientQuestionsError(
                f"Item bank has only {available} '{difficulty.value}' question(s), but "
                f"{count} are needed per variant under the configured difficulty "
                f"distribution {({d.value: f for d, f in distribution.items()})}. "
                f"Add more '{difficulty.value}' questions, or pass a different "
                f"difficulty_distribution for this compile."
            )

    for _ in range(num_variants):
        selected: List[Question] = []
        for difficulty, count in counts_per_difficulty.items():
            bucket = by_difficulty.get(difficulty, [])
            already_in_this_variant = {q.id for q in selected}

            fresh_candidates = [q for q in bucket if q.id not in used_globally]
            picked = _pick_topic_diverse(fresh_candidates, count, already_in_this_variant)

            if len(picked) < count:
                remaining_needed = count - len(picked)
                picked_ids = {q.id for q in picked}
                fallback_pool = [
                    q for q in bucket
                    if q.id not in picked_ids and q.id not in already_in_this_variant
                ]
                random.shuffle(fallback_pool)
                picked.extend(fallback_pool[:remaining_needed])

            selected.extend(picked)

        used_globally.update(q.id for q in selected)
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