"""Run once to seed the database with comprehensive test data."""
import app.models  # noqa: F401
import time
from app.db import SessionLocal
from app.models.user import User, UserRole
from app.models.device import Device
from app.models.exam_centre import ExamCentre
from app.models.question import Question
from app.models.access_attempt import AccessAttempt
from app.services import auth_service

from app.models.exam_event import ExamEvent, ExamEventStatus
from app.models.ledger_entry import LedgerEventType
from app.services import ledger_service, variant_assignment

db = SessionLocal()

print("Seeding database for Admin Demo...")

# 1. CREATE CUSTODIANS
custodian_types_emails = [
    "board_rep@pardarshi.local",
    "regulator@pardarshi.local",
    "magistrate@pardarshi.local",
    "state_officer@pardarshi.local",
    "auditor_cust@pardarshi.local",
]
custodian_ids = []
for email in custodian_types_emails:
    u = User(
        email=email,
        password_hash=auth_service.hash_password("TestPass123!"),
        role=UserRole.CUSTODIAN,
        full_name=email.split("@")[0].replace("_", " ").title(),
        is_active=True
    )
    db.add(u)
    db.flush()
    custodian_ids.append(str(u.id))

# 2. CREATE ACTIVE & PENDING USERS
admin = User(
    email="admin_demo@pardarshi.local",
    password_hash=auth_service.hash_password("TestPass123!"),
    role=UserRole.ADMIN,
    full_name="System Admin",
    is_active=True
)
db.add(admin)

operator = User(
    email="operator@pardarshi.local",
    password_hash=auth_service.hash_password("TestPass123!"),
    role=UserRole.CENTRE_OPERATOR,
    full_name="Active Operator",
    is_active=True
)
db.add(operator)
db.flush()

pending_operator = User(
    email="new_operator@pardarshi.local",
    password_hash=auth_service.hash_password("TestPass123!"),
    role=UserRole.CENTRE_OPERATOR,
    full_name="Pending Operator",
    is_active=False
)
db.add(pending_operator)
db.flush()

# 3. CREATE PENDING DEVICE (mapped to older `is_active` instead of `is_approved`)
pending_device = Device(
    user_id=operator.id,
    fingerprint="mock-fingerprint-a1b2c3d4",
    is_active=False
)
db.add(pending_device)

# 4. CREATE EXAM CENTRES
centres = [
    ExamCentre(centre_code="PUNE-042", name="VIT Pune Campus", latitude=18.4636, longitude=73.8681, acceptable_radius_m=500),
    ExamCentre(centre_code="PUNE-018", name="COEP Main Building", latitude=18.5293, longitude=73.8566, acceptable_radius_m=500),
    ExamCentre(centre_code="MUM-105", name="VJTI Mumbai", latitude=19.0222, longitude=72.8561, acceptable_radius_m=500),
]
db.add_all(centres)
db.flush()

# 5. CREATE ITEM BANK QUESTIONS (mapped to contributor_id, topic, and tags)
topics = ["Data Structures", "Algorithms", "Cryptography", "Database Systems"]
questions = []
for i in range(30):
    q = Question(
        contributor_id=admin.id,
        encrypted_content=f"enc_mock_data_{i}_v1_aes256",
        topic=topics[i % 4],
        tags=["mock", "mid_sem_review"]
    )
    questions.append(q)
db.add_all(questions)

# 6. CREATE FLAGGED ACCESS ATTEMPTS (mapped to boolean check columns)
attempts = [
    AccessAttempt(
        user_id=operator.id,
        action="unlock_paper",
        role_check_passed=True,
        device_check_passed=False,  # Fails device check
        location_check_passed=True,
        time_window_check_passed=True,
        overall_passed=False
    ),
    AccessAttempt(
        user_id=operator.id,
        action="unlock_paper",
        role_check_passed=True,
        device_check_passed=True,
        location_check_passed=True,
        time_window_check_passed=False, # Fails time check
        overall_passed=False
    )
]
db.add_all(attempts)

# Commit all test data
db.commit()

print("\n=== DEMO DATA SEEDED SUCCESSFULLY ===")
print("\nAdmin Login: admin_demo@pardarshi.local / TestPass123!")
print("\nCustodian user IDs (Use these in the Compile Paper form):")
for email, cid in zip(custodian_types_emails, custodian_ids):
    print(f"  {email}: {cid}")
    
print("\nTest Exam Centres Created:")
for c in centres:
    print(f"  {c.name} ({c.centre_code})")

print("\nPending Approvals:")
print("  1 User Account pending")
print("  1 Device Registration pending")
print("  30 Questions added to Item Bank")
print("  2 Flagged Security Events generated")

print("Generating cryptographic ledger entries and active exam events...")

# Create a Draft Exam Event for the Overview Dashboard
secret = variant_assignment.generate_assignment_secret()
demo_event = ExamEvent(
    exam_name="Mid-Sem Demo Examination",
    exam_start_epoch=time.time() + 86400,  # Starts tomorrow
    override_window_end_epoch=time.time() + 90000,
    num_variants=2,
    threshold=3,
    total_custodians=5,
    override_threshold=2,
    assignment_secret_hash=variant_assignment.hash_secret_for_storage(secret),
    status=ExamEventStatus.DRAFT,
    created_by=admin.id
)
db.add(demo_event)
db.commit()

# Safely append actions to the hash-chained ledger
ledger_service.append(
    db, 
    LedgerEventType.QUESTION_SUBMITTED, 
    details={"message": "Initial item bank seeded with 30 questions"}, 
    actor_id=admin.id
)

print("Dashboard and Ledger successfully populated!")