"""
SQLAlchemy ORM models for the patent intelligence platform.
Maps to Neon PostgreSQL with pgvector support.
"""

import uuid
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    String, Text, Boolean, Integer, Float, Date, DateTime,
    ForeignKey, JSON, Index, UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


# ---------------------------------------------------------------------------
# Firm & User (multi-tenant)
# ---------------------------------------------------------------------------

class Firm(Base):
    __tablename__ = "firms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    clerk_org_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="firm", cascade="all, delete-orphan")
    patents: Mapped[List["Patent"]] = relationship(back_populates="firm", cascade="all, delete-orphan")
    patent_families: Mapped[List["PatentFamily"]] = relationship(back_populates="firm", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), default="attorney"
    )  # admin, attorney, paralegal
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    firm: Mapped["Firm"] = relationship(back_populates="users")
    drafts: Mapped[List["Draft"]] = relationship(back_populates="created_by_user")


# ---------------------------------------------------------------------------
# Patent Core
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Patent Family
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Office Actions
# ---------------------------------------------------------------------------

class OfficeAction(Base):
    __tablename__ = "office_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patents.id", ondelete="CASCADE"), nullable=False
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


# ---------------------------------------------------------------------------
# Prior Art
# ---------------------------------------------------------------------------

class PriorArtReference(Base):
    __tablename__ = "prior_art_references"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patents.id", ondelete="CASCADE"), nullable=False
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


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------

class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patents.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    draft_type: Mapped[str] = mapped_column(
        String(50), default="application"
    )  # application, response, amendment
    ai_model_used: Mapped[Optional[str]] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(
        String(50), default="draft"
    )  # draft, review, finalized
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    patent: Mapped[Optional["Patent"]] = relationship(back_populates="drafts")
    created_by_user: Mapped["User"] = relationship(back_populates="drafts")


# ---------------------------------------------------------------------------
# Embeddings (pgvector) — stored as raw vector columns
# These will use the `vector` type from pgvector extension
# ---------------------------------------------------------------------------

class PatentEmbedding(Base):
    """Chunked embeddings for full patent documents.
    Each row: [patent_id, chunk_text, vector(1024), page_number, section_type, firm_id]
    """
    __tablename__ = "patent_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # The embedding column is created via raw SQL migration with pgvector
    # embedding vector(1024)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    section_type: Mapped[Optional[str]] = mapped_column(String(50), default="description")
    firm_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    patent: Mapped["Patent"] = relationship(back_populates="embeddings")


class ClaimEmbedding(Base):
    """Individual claim embeddings for precise semantic search."""
    __tablename__ = "claim_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patent_claims.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # embedding vector(1024) — via raw SQL migration
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    claim: Mapped["PatentClaim"] = relationship(back_populates="embedding")
