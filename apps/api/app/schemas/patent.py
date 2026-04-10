import uuid
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel

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
