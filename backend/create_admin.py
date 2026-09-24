"""Run once to create your first real admin user for manual testing."""
import app.models  # noqa: F401
from app.db import SessionLocal
from app.models.user import User, UserRole
from app.services import auth_service

db = SessionLocal()
admin = User(
    email="admin@pardarshi.local",
    password_hash=auth_service.hash_password("Test@123"),
    role=UserRole.ADMIN,
    full_name="System Admin",
)
db.add(admin)
db.commit()
print("Admin created:", admin.id, admin.email)