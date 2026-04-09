import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String, Text, Boolean, Integer, ForeignKey, Index, UniqueConstraint,
    Date, DateTime, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base

class Patent(Base):
    __tablename__ = "patents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False, index=True
    )
    application_number: Mapped[str] = mapped_column(String(50), nullable=False)
    patent_number: Mapped[Optional[str]] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, granted, abandoned, expired
    filing_date: Mapped[Optional[date]] = mapped_column(Date)
    grant_date: Mapped[Optional[date]] = mapped_column(Date)
    priority_date: Mapped[Optional[date]] = mapped_column(Date)
    inventors: Mapped[Optional[dict]] = mapped_column(JSONB, default=[])
    assignee: Mapped[Optional[str]] = mapped_column(String(500))
    classification: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    patent_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default={})
    family_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patent_families.id"), nullable=True
    )
    
    # Soft Delete Support
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    firm: Mapped["Firm"] = relationship(back_populates="patents")
    family: Mapped[Optional["PatentFamily"]] = relationship(back_populates="patents")
    claims: Mapped[List["PatentClaim"]] = relationship(
        back_populates="patent", cascade="all, delete-orphan"
    )
    office_actions: Mapped[List["OfficeAction"]] = relationship(
        back_populates="patent", cascade="all, delete-orphan"
    )
    prior_art_refs: Mapped[List["PriorArtReference"]] = relationship(
        back_populates="patent", cascade="all, delete-orphan"
    )
    embeddings: Mapped[List["PatentEmbedding"]] = relationship(
        back_populates="patent", cascade="all, delete-orphan"
    )
    drafts: Mapped[List["Draft"]] = relationship(
        back_populates="patent", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_patents_firm_status", "firm_id", "status"),
        Index("idx_patents_application_number", "application_number"),
        UniqueConstraint("firm_id", "application_number", name="uq_firm_application"),
    )


class PatentClaim(Base):
    __tablename__ = "patent_claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patents.id", ondelete="CASCADE"), nullable=False
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_number: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_independent: Mapped[bool] = mapped_column(Boolean, default=False)
    depends_on: Mapped[Optional[int]] = mapped_column(Integer)  # parent claim number
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    patent: Mapped["Patent"] = relationship(back_populates="claims")
    embedding: Mapped[Optional["ClaimEmbedding"]] = relationship(
        back_populates="claim", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("patent_id", "claim_number", name="uq_patent_claim_number"),
    )


class PatentFamily(Base):
    __tablename__ = "patent_families"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False, index=True
    )
    family_name: Mapped[str] = mapped_column(String(500), nullable=False)
    family_external_id: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    firm: Mapped["Firm"] = relationship(back_populates="patent_families")
    patents: Mapped[List["Patent"]] = relationship(back_populates="family")
