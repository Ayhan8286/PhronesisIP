import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base

class PriorArtReference(Base):
    __tablename__ = "prior_art_references"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patents.id", ondelete="CASCADE"), nullable=False
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reference_number: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_title: Mapped[Optional[str]] = mapped_column(Text)
    reference_abstract: Mapped[Optional[str]] = mapped_column(Text)
    reference_type: Mapped[str] = mapped_column(
        String(50), default="patent"
    )  # patent, npl (non-patent literature)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    cited_by_examiner: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    patent: Mapped["Patent"] = relationship(back_populates="prior_art_refs")
