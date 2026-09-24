import app.models  # noqa: F401
from app.db import SessionLocal
from app.models.user import User
from app.models.device import Device
from app.models.ledger_entry import LedgerEventType
from app.services import ledger_service

db = SessionLocal()

print("Appending approval records to the Audit Ledger...")

# Get the admin to act as the "actor"
admin = db.query(User).filter_by(email="admin_demo@pardarshi.local").first()
pending_user = db.query(User).filter_by(email="new_operator@pardarshi.local").first()
pending_device = db.query(Device).first()

if admin:
    # 1. Log the User Approval
    if pending_user:
        ledger_service.append(
            db, 
            # If your older codebase has LedgerEventType.ACCOUNT_APPROVED, use that instead!
            LedgerEventType.QUESTION_SUBMITTED, 
            details={
                "action": "ACCOUNT_APPROVED",
                "target_user_email": pending_user.email,
                "message": f"Administrator approved new account for {pending_user.email}"
            }, 
            actor_id=admin.id
        )
        print("Logged User Approval.")

    # 2. Log the Device Approval
    if pending_device:
        ledger_service.append(
            db, 
            LedgerEventType.QUESTION_SUBMITTED, 
            details={
                "action": "DEVICE_APPROVED",
                "device_fingerprint": pending_device.fingerprint,
                "message": "Administrator approved new device registration."
            }, 
            actor_id=admin.id
        )
        print("Logged Device Approval.")

    db.commit()
    print("Audit Ledger successfully updated with cryptographic hashes!")
else:
    print("Admin user not found. Did you run the seed script?")