import uuid
from typing import Optional, List
from pydantic import BaseModel, Field

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

class PriorArtAnalysisRequest(BaseModel):
    patent_id: uuid.UUID
    analysis_depth: str = "standard"  # quick, standard, deep
    include_npl: bool = False

class RiskAnalysisRequest(BaseModel):
    patent_id: uuid.UUID
    target_claims: Optional[List[int]] = None  # specific claim numbers, or all
    analysis_type: str = "invalidity"  # invalidity, infringement, freedom-to-operate
