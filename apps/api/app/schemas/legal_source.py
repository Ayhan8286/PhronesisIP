"""
Pydantic schemas for the Legal Knowledge Base API.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Legal Source Schemas ────────────────────────────────────────────────────

class LegalSourceCreate(BaseModel):
    """Request body for uploading a new legal source."""
    jurisdiction: str = Field(
        ...,
        description="Jurisdiction code: USPTO, EPO, JPO, CNIPA, IP_AUSTRALIA, WIPO, firm"
    )
    doc_type: str = Field(
        ...,
        description="Document type: statute, rule, guideline, firm_policy, case_law"
    )
    title: str = Field(..., min_length=1, max_length=500)
    version: Optional[str] = Field(None, max_length=50)
    source_updated_at: Optional[datetime] = Field(
        None,
        description="When the actual legal document was last updated/revised"
    )
    is_global: bool = Field(
        False,
        description="If true, source is available to all firms (admin-only)"
    )


class LegalSourceUpdate(BaseModel):
    """Request body for updating a legal source."""
    is_active: Optional[bool] = None
    title: Optional[str] = Field(None, max_length=500)
    version: Optional[str] = Field(None, max_length=50)
    source_updated_at: Optional[datetime] = None


class LegalSourceResponse(BaseModel):
    """Response body for a legal source."""
    id: uuid.UUID
    firm_id: Optional[uuid.UUID]
    jurisdiction: str
    doc_type: str
    title: str
    version: Optional[str]
    status: str
    is_active: bool
    chunk_count: int
    source_updated_at: Optional[datetime]
    is_stale: bool = Field(
        False,
        description="True if source_updated_at is older than 12 months"
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LegalSourceChunkResponse(BaseModel):
    """Response body for previewing a chunk."""
    id: uuid.UUID
    chunk_text: str
    section: Optional[str]
    page_number: Optional[int]
    chunk_index: int

    model_config = {"from_attributes": True}


# ── Jurisdiction Schemas ────────────────────────────────────────────────────

class JurisdictionStatus(BaseModel):
    """Status of legal sources for a specific jurisdiction."""
    jurisdiction: str
    source_count: int
    total_chunks: int
    has_sources: bool
    is_stale: bool
    oldest_source_date: Optional[str]


class JurisdictionListItem(BaseModel):
    """Summary of a jurisdiction with source counts."""
    jurisdiction: str
    source_count: int
    total_chunks: int


# ── Citation Validation Schemas ─────────────────────────────────────────────

class CitationValidationResponse(BaseModel):
    """Citation validation results returned with AI output."""
    is_valid: bool
    total_citations: int
    valid_citations: List[str]
    invalid_citations: List[str]
    uncited_claims: List[str]
    attorney_review_items: List[str]
    warning: bool


class SourceUsedResponse(BaseModel):
    """Metadata about a legal source used in generation (for UI trust panel)."""
    title: str
    section: str
    jurisdiction: str
    doc_type: str
    score: float
