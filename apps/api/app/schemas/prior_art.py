import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

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
