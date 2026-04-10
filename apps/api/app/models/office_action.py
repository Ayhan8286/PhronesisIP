import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Text, Integer, ForeignKey, Date, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base

class OfficeAction(Base):
    __tablename__ = "office_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patents.id", ondelete="CASCADE"), nullable=False
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # non-final, final, restriction, advisory
    mailing_date: Mapped[Optional[date]] = mapped_column(Date)
    response_deadline: Mapped[Optional[date]] = mapped_column(Date)
    r2_file_key: Mapped[Optional[str]] = mapped_column(String(500))
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    rejections: Mapped[Optional[dict]] = mapped_column(JSONB, default=[])
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, responded, appeal
    
    # Soft Delete Support
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    patent: Mapped["Patent"] = relationship(back_populates="office_actions")
    response_drafts: Mapped[List["OAResponseDraft"]] = relationship(
        back_populates="office_action", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_oa_patent_status", "patent_id", "status"),
        Index("idx_oa_deadline", "response_deadline"),
    )


class OAResponseDraft(Base):
    __tablename__ = "oa_response_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    office_action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("office_actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_content: Mapped[str] = mapped_column(Text, nullable=False)
    ai_model_used: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(50), default="draft"
    )  # draft, review, approved, submitted
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    office_action: Mapped["OfficeAction"] = relationship(back_populates="response_drafts")
