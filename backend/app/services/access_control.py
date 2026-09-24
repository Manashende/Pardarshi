"""
Module 5 / Algorithm D — the access-control gate. Every sensitive
action passes through check_access() before proceeding. All four
conditions must pass; failure on ANY single one is a hard block (the
caller must refuse the action, not just log a warning). An AccessAttempt
row is written regardless of outcome, feeding the admin dashboard's
"flagged access attempts" panel (Module 9).
"""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from geopy.distance import geodesic
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.device import Device
from app.models.access_attempt import AccessAttempt


@dataclass
class AccessCheckResult:
    role_check_passed: bool
    device_check_passed: bool
    location_check_passed: bool
    time_window_check_passed: bool
    overall_passed: bool
    reason: Optional[str]


def _check_role(user: User, allowed_roles: list) -> bool:
    return user.role in allowed_roles


def _check_device(db: Session, user: User, device_fingerprint: Optional[str]) -> bool:
    """Fails closed — no fingerprint provided is treated as untrusted, never waved through."""
    if not device_fingerprint:
        return False
    device = (
        db.query(Device)
        .filter(Device.user_id == user.id, Device.fingerprint == device_fingerprint, Device.is_active == True)  # noqa: E712
        .first()
    )
    return device is not None


def _check_location(declared_lat, declared_lon, expected_lat, expected_lon, acceptable_radius_m) -> bool:
    """Fails closed if either point is missing."""
    if declared_lat is None or declared_lon is None or expected_lat is None or expected_lon is None:
        return False
    distance_m = geodesic((declared_lat, declared_lon), (expected_lat, expected_lon)).meters
    return distance_m <= acceptable_radius_m


def _check_time_window(now_epoch, window_start, window_end) -> bool:
    """Fails closed if a window was required but not provided."""
    if window_start is None or window_end is None:
        return False
    return window_start <= now_epoch <= window_end


def check_access(
    db: Session,
    user: User,
    action: str,
    allowed_roles: list,
    now_epoch: float,
    device_fingerprint: Optional[str] = None,
    declared_lat: Optional[float] = None,
    declared_lon: Optional[float] = None,
    expected_lat: Optional[float] = None,
    expected_lon: Optional[float] = None,
    acceptable_radius_m: float = 500.0,
    window_start: Optional[float] = None,
    window_end: Optional[float] = None,
    location_required: bool = True,
    time_window_required: bool = True,
) -> AccessCheckResult:
    role_ok = _check_role(user, allowed_roles)
    device_ok = _check_device(db, user, device_fingerprint)
    location_ok = (
        _check_location(declared_lat, declared_lon, expected_lat, expected_lon, acceptable_radius_m)
        if location_required else True
    )
    time_ok = (
        _check_time_window(now_epoch, window_start, window_end)
        if time_window_required else True
    )

    overall = role_ok and device_ok and location_ok and time_ok

    reason = None
    if not overall:
        if not role_ok:
            reason = f"role '{user.role.value}' not permitted for action '{action}'"
        elif not device_ok:
            reason = "device not recognized or not active"
        elif not location_ok:
            reason = "declared location outside acceptable radius"
        elif not time_ok:
            reason = "outside permitted time window for this action"

    attempt = AccessAttempt(
        user_id=user.id,
        action=action,
        role_check_passed=role_ok,
        device_check_passed=device_ok,
        location_check_passed=location_ok,
        time_window_check_passed=time_ok,
        overall_passed=overall,
        declared_latitude=declared_lat,
        declared_longitude=declared_lon,
    )
    db.add(attempt)
    db.flush()

    return AccessCheckResult(
        role_check_passed=role_ok,
        device_check_passed=device_ok,
        location_check_passed=location_ok,
        time_window_check_passed=time_ok,
        overall_passed=overall,
        reason=reason,
    )