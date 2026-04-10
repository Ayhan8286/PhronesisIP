import uuid
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel

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
