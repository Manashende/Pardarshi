"""
/auth/login — matches docs/openapi.yaml's LoginRequest/LoginResponse
schema, including device_fingerprint handling.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import auth_service
from app.models.user import User, UserRole
from app.models.device import Device

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str
    device_fingerprint: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    full_name: str


class LoginResponse(BaseModel):
    access_token: str
    user: UserOut
    device_registered: bool


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    requested_role: UserRole


class RegisterResponse(BaseModel):
    id: str
    message: str


@router.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email already registered")

    user = User(
        email=req.email,
        password_hash=auth_service.hash_password(req.password),
        full_name=req.full_name,
        role=req.requested_role,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return RegisterResponse(id=str(user.id), message="Registered — awaiting admin approval before you can log in.")

@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if user is None or not auth_service.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account pending admin approval")

    device = (
        db.query(Device)
        .filter(Device.user_id == user.id, Device.fingerprint == req.device_fingerprint)
        .first()
    )
    device_registered = device is not None and device.is_active

    token = auth_service.create_access_token(user.id, user.role.value)

    return LoginResponse(
        access_token=token,
        user=UserOut(id=str(user.id), email=user.email, role=user.role.value, full_name=user.full_name),
        device_registered=device_registered,
    )