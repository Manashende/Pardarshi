import uuid
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class PrintJob(Base):
    """
    Module 7 — one simulated printer's dispatch at one centre for one
    variant. A single unlock event typically creates several PrintJob
    rows (one per simulated_printer_id) so copies_assigned splits across
    them — this is what "parallelized dispatch" means in the data model.
    """
    __tablename__ = "print_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("paper_variants.id"), nullable=False)
    centre_id = Column(UUID(as_uuid=True), ForeignKey("exam_centres.id"), nullable=False)
    simulated_printer_id = Column(Integer, nullable=False)
    copies_assigned = Column(Integer, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)