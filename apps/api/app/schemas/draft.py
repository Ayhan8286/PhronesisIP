import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

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

class DraftGenerationRequest(BaseModel):
    invention_description: Optional[str] = None
    description: Optional[str] = None  # alias from frontend
    technical_field: str = ""
    prior_art_context: Optional[str] = None
    claim_style: str = "apparatus"  # apparatus, method, system, composition
    spec_context: Optional[str] = None  # extracted text from uploaded engineering spec
    jurisdiction: Optional[str] = None  # USPTO, EPO, etc. — enables strict legal RAG
    patent_id: Optional[str] = None  # for patent-specific context retrieval

class OAResponseGenerationRequest(BaseModel):
    response_strategy: str = "argue"  # argue, amend, both
    additional_context: Optional[str] = None
    jurisdiction: Optional[str] = None  # USPTO, EPO, etc. — enables strict legal RAG
