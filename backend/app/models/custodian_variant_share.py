import uuid
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class CustodianVariantShare(Base):
    """
    Fixes a real gap: Custodian (user, exam_event, custodian_type, share_x)
    identifies WHO a custodian is and their fixed x-coordinate — stable
    across every variant of one exam event. But each variant has its
    OWN independently-generated AES key, so each variant needs its OWN
    y-value for that same custodian's x. This table holds that
    per-variant y-value; Custodian itself no longer stores share_y.
    """
    __tablename__ = "custodian_variant_shares"
    __table_args__ = (
        UniqueConstraint("custodian_id", "variant_id", name="uq_custodian_variant"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    custodian_id = Column(UUID(as_uuid=True), ForeignKey("custodians.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("paper_variants.id"), nullable=False)
    share_y_encrypted = Column(String, nullable=False)