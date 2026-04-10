import uuid
from datetime import datetime
from pydantic import BaseModel

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
