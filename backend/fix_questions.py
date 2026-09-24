import app.models  # noqa: F401
from app.db import SessionLocal
from app.models.question import Question
from app.services import item_bank_service

db = SessionLocal()

print("Encrypting existing mock questions...")
questions = db.query(Question).all()

for i, q in enumerate(questions):
    # Use the actual service to generate a mathematically valid JSON crypto bundle
    valid_crypto_json = item_bank_service.encrypt_question_content(
        f"This is mock question {i} for the mid-sem review demonstration. What is the correct answer?"
    )
    q.encrypted_content = valid_crypto_json

db.commit()
print(f"Successfully fixed {len(questions)} questions!")