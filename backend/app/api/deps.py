"""
get_current_user is the dependency every protected route uses. It reads
the Authorization: Bearer <token> header, validates it, loads the User
from DB, and makes it available to the route function. require_role()
builds on top of it for role-gated routes.
"""
import uuid
from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import auth_service
from app.models.user import User, UserRole

_bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = auth_service.decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")

    # JWT claims are always strings — must convert back to a real UUID
    # object before querying a UUID column, or the comparison silently
    # breaks depending on the DB driver.
    raw_user_id = payload.get("sub")
    try:
        user_id = uuid.UUID(raw_user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token subject")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user no longer exists")

    return user


def require_role(allowed_roles: List[UserRole]):
    """
    Usage: current_user: User = Depends(require_role([UserRole.ADMIN]))
    This is the ROLE check of Algorithm D's four conditions; the other
    three (device/location/time) are handled separately by
    app.services.access_control.check_access for actions that need them.
    """
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{current_user.role.value}' not permitted for this action",
            )
        return current_user
    return _dependency