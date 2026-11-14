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
    acceptable_radius_m = Column(Integer, nullable=False, default=500, server_default='500')
    # Needed by Module 7's print dispatch to know how many copies to
    # split across the centre's simulated printers.
    expected_candidate_count = Column(Integer, nullable=False, default=100, server_default='100')
    # Was previously a hardcoded `num_printers=4` inside unlock() itself,
    # meaning every centre got the same printer count regardless of its
    # actual size. Now a real per-centre property, same treatment as
    # acceptable_radius_m and expected_candidate_count above.
    # NOTE: `default=` is an application-level default (ORM inserts only);
    # `server_default=` is what actually backfills existing rows during a
    # migration — both are needed, not just one.
    num_printers = Column(Integer, nullable=False, default=4, server_default='4')