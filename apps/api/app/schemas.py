"""
Pydantic schemas for request/response serialization.
"""

import uuid
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Firm
# ---------------------------------------------------------------------------

class FirmBase(BaseModel):
    name: str
    clerk_org_id: str


class FirmCreate(FirmBase):
    pass


class FirmResponse(FirmBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Patent
# ---------------------------------------------------------------------------

class PatentBase(BaseModel):
    application_number: str
    title: str
    abstract: Optional[str] = None
    status: str = "pending"
    filing_date: Optional[date] = None
    grant_date: Optional[date] = None
    priority_date: Optional[date] = None
    inventors: Optional[List[dict]] = []
    assignee: Optional[str] = None
    classification: Optional[dict] = {}


class PatentCreate(PatentBase):
    family_id: Optional[uuid.UUID] = None


class PatentUpdate(BaseModel):
    title: Optional[str] = None
    abstract: Optional[str] = None
    status: Optional[str] = None
    grant_date: Optional[date] = None
    assignee: Optional[str] = None
    family_id: Optional[uuid.UUID] = None


class PatentResponse(PatentBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    patent_number: Optional[str] = None
    family_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatentListResponse(BaseModel):
    patents: List[PatentResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Patent Claims
# ---------------------------------------------------------------------------

class ClaimBase(BaseModel):
    claim_number: int
    claim_text: str
    is_independent: bool = False
    depends_on: Optional[int] = None


class ClaimCreate(ClaimBase):
    pass


class ClaimResponse(ClaimBase):
    id: uuid.UUID
    patent_id: uuid.UUID

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Patent Family
# ---------------------------------------------------------------------------

class PatentFamilyBase(BaseModel):
    family_name: str
    family_external_id: Optional[str] = None
    description: Optional[str] = None


class PatentFamilyCreate(PatentFamilyBase):
    pass


class PatentFamilyResponse(PatentFamilyBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    created_at: datetime
    patents: Optional[List[PatentResponse]] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Office Actions
# ---------------------------------------------------------------------------

class OfficeActionBase(BaseModel):
    action_type: str
    mailing_date: Optional[date] = None
    response_deadline: Optional[date] = None


class OfficeActionCreate(OfficeActionBase):
    patent_id: uuid.UUID


class OfficeActionResponse(OfficeActionBase):
    id: uuid.UUID
    patent_id: uuid.UUID
    status: str
    r2_file_key: Optional[str] = None
    extracted_text: Optional[str] = None
    rejections: Optional[List[dict]] = []
    created_at: datetime

    class Config:
        from_attributes = True


class OAResponseDraftCreate(BaseModel):
    draft_content: str


class OAResponseDraftResponse(BaseModel):
    id: uuid.UUID
    office_action_id: uuid.UUID
    draft_content: str
    ai_model_used: Optional[str] = None
    status: str
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Prior Art
# ---------------------------------------------------------------------------

class PriorArtBase(BaseModel):
    reference_number: str
    reference_title: Optional[str] = None
    reference_abstract: Optional[str] = None
    reference_type: str = "patent"
    relevance_score: Optional[float] = None
    cited_by_examiner: bool = False
    analysis_notes: Optional[str] = None


class PriorArtCreate(PriorArtBase):
    patent_id: uuid.UUID


class PriorArtResponse(PriorArtBase):
    id: uuid.UUID
    patent_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------

class DraftBase(BaseModel):
    title: str
    content: str = ""
    draft_type: str = "application"


class DraftCreate(DraftBase):
    patent_id: Optional[uuid.UUID] = None


class DraftUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


class DraftResponse(DraftBase):
    id: uuid.UUID
    patent_id: Optional[uuid.UUID] = None
    firm_id: uuid.UUID
    created_by: uuid.UUID
    ai_model_used: Optional[str] = None
    version: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=20, ge=1, le=100)
    search_type: str = "hybrid"  # semantic, keyword, hybrid
    filters: Optional[dict] = None  # status, date range, classification


class SearchResultItem(BaseModel):
    patent_id: uuid.UUID
    title: str
    application_number: str
    score: float
    matched_text: str
    status: str


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    query: str
    total: int


# ---------------------------------------------------------------------------
# AI Generation
# ---------------------------------------------------------------------------

class DraftGenerationRequest(BaseModel):
    invention_description: Optional[str] = None
    description: Optional[str] = None  # alias from frontend
    technical_field: str = ""
    prior_art_context: Optional[str] = None
    claim_style: str = "apparatus"  # apparatus, method, system, composition
    spec_context: Optional[str] = None  # extracted text from uploaded engineering spec


class OAResponseGenerationRequest(BaseModel):
    response_strategy: str = "argue"  # argue, amend, both
    additional_context: Optional[str] = None


class PriorArtAnalysisRequest(BaseModel):
    patent_id: uuid.UUID
    analysis_depth: str = "standard"  # quick, standard, deep
    include_npl: bool = False


class RiskAnalysisRequest(BaseModel):
    patent_id: uuid.UUID
    target_claims: Optional[List[int]] = None  # specific claim numbers, or all
    analysis_type: str = "invalidity"  # invalidity, infringement, freedom-to-operate
