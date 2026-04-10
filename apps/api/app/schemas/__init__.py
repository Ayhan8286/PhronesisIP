"""
Domain-driven Pydantic schemas.
"""
from .firm import FirmBase, FirmCreate, FirmResponse
from .patent import (
    PatentBase, PatentCreate, PatentUpdate, PatentResponse, PatentListResponse,
    ClaimBase, ClaimCreate, ClaimResponse,
    PatentFamilyBase, PatentFamilyCreate, PatentFamilyResponse
)
from .office_action import (
    OfficeActionBase, OfficeActionCreate, OfficeActionResponse,
    OAResponseDraftCreate, OAResponseDraftResponse
)
from .prior_art import PriorArtBase, PriorArtCreate, PriorArtResponse
from .draft import DraftBase, DraftCreate, DraftUpdate, DraftResponse, DraftGenerationRequest, OAResponseGenerationRequest
from .search import SemanticSearchRequest, SearchResultItem, SearchResponse, PriorArtAnalysisRequest, RiskAnalysisRequest

__all__ = [
    "FirmBase", "FirmCreate", "FirmResponse",
    "PatentBase", "PatentCreate", "PatentUpdate", "PatentResponse", "PatentListResponse",
    "ClaimBase", "ClaimCreate", "ClaimResponse",
    "PatentFamilyBase", "PatentFamilyCreate", "PatentFamilyResponse",
    "OfficeActionBase", "OfficeActionCreate", "OfficeActionResponse",
    "OAResponseDraftCreate", "OAResponseDraftResponse",
    "PriorArtBase", "PriorArtCreate", "PriorArtResponse",
    "DraftBase", "DraftCreate", "DraftUpdate", "DraftResponse", "DraftGenerationRequest", "OAResponseGenerationRequest",
    "SemanticSearchRequest", "SearchResultItem", "SearchResponse", "PriorArtAnalysisRequest", "RiskAnalysisRequest"
]
