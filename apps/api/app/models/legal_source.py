"""
Legal Knowledge Base models.

LegalSource: metadata about an uploaded legal document (MPEP, statute, firm policy, etc.)
LegalSourceChunk: chunked text + vector embedding from that document, used for strict RAG retrieval.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class LegalSource(Base):
    """Metadata for an uploaded legal reference document."""
    __tablename__ = "legal_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    firm_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=True, index=True
    )  # NULL = global source (MPEP, statutes), populated = firm-specific
    jurisdiction: Mapped[str] = mapped_column(
        String(50), nullable=False, default="USPTO"
    )  # USPTO | EPO | JPO | CNIPA | IP_AUSTRALIA | WIPO | firm
    doc_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="guideline"
    )  # statute | rule | guideline | firm_policy | case_law
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(50))
    r2_key: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    source_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    chunks: Mapped[List["LegalSourceChunk"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    firm: Mapped[Optional["Firm"]] = relationship()
    uploader: Mapped[Optional["User"]] = relationship()


class LegalSourceChunk(Base):
    """A chunked text segment from a legal source, with vector embedding for RAG retrieval."""
    __tablename__ = "legal_source_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_sources.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    firm_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=True, index=True
    )  # Denormalized from LegalSource for RLS filtering
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    section: Mapped[Optional[str]] = mapped_column(String(200))
    # e.g. "35 U.S.C. § 112", "MPEP § 2111.01", "Rule 43 EPC"
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    source: Mapped["LegalSource"] = relationship(back_populates="chunks")
