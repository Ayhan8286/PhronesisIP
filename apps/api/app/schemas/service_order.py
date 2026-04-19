from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class ServiceOrderCreate(BaseModel):
    client_email: EmailStr
    client_name: Optional[str] = None
    service_package: str = Field(..., pattern="^(prior_art|patentability|office_action)$")
    description: Optional[str] = None
    uploaded_file_key: Optional[str] = None

class ServiceOrderResponse(BaseModel):
    id: UUID
    client_email: str
    client_name: Optional[str]
    service_package: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
