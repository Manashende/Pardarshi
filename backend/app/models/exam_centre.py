import uuid
from sqlalchemy import Column, String, Float, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class ExamCentre(Base):
    __tablename__ = "exam_centres"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    centre_code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    acceptable_radius_m = Column(Integer, nullable=False, default=500)
    # Needed by Module 7's print dispatch to know how many copies to
    # split across the centre's simulated printers.
    expected_candidate_count = Column(Integer, nullable=False, default=100)