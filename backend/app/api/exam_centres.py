"""
Exam centre management. Any authenticated role can LIST centres (a
custodian or operator needs to see the centre list too), but only
ADMIN can CREATE one — centre registration is an institutional act,
not something any role self-serves.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.exam_centre import ExamCentre

router = APIRouter(prefix="/exam-centres", tags=["exam-centres"])


class CreateCentreRequest(BaseModel):
    centre_code: str
    name: str
    latitude: float
    longitude: float
    acceptable_radius_m: int = 500
    expected_candidate_count: int = 100


class CentreOut(BaseModel):
    id: str
    centre_code: str
    name: str
    latitude: float
    longitude: float
    acceptable_radius_m: int
    expected_candidate_count: int


@router.post("", response_model=CentreOut)
def create_centre(
    req: CreateCentreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    existing = db.query(ExamCentre).filter(ExamCentre.centre_code == req.centre_code).first()
    if existing:
        raise HTTPException(400, "centre_code already exists")
    centre = ExamCentre(**req.model_dump())
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return CentreOut(
        id=str(centre.id), centre_code=centre.centre_code, name=centre.name,
        latitude=centre.latitude, longitude=centre.longitude,
        acceptable_radius_m=centre.acceptable_radius_m,
        expected_candidate_count=centre.expected_candidate_count,
    )


@router.get("", response_model=list[CentreOut])
def list_centres(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(list(UserRole))),
):
    centres = db.query(ExamCentre).order_by(ExamCentre.centre_code).all()
    return [
        CentreOut(
            id=str(c.id), centre_code=c.centre_code, name=c.name,
            latitude=c.latitude, longitude=c.longitude,
            acceptable_radius_m=c.acceptable_radius_m,
            expected_candidate_count=c.expected_candidate_count,
        )
        for c in centres
    ]