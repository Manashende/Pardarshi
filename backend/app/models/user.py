import uuid
import enum
from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy import Column, String, DateTime, Enum, Boolean

from app.db import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    CONTRIBUTOR = "CONTRIBUTOR"
    CUSTODIAN = "CUSTODIAN"
    CENTRE_OPERATOR = "CENTRE_OPERATOR"
    AUDITOR = "AUDITOR"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default='true')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # NOTE: no forward reference to Device here on purpose. Device already
    # points back to User via user_id — a bidirectional FK creates a
    # circular dependency that breaks table-creation ordering. To find a
    # user's device, query Device WHERE user_id = this user's id.