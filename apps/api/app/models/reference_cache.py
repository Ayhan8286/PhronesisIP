import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base

class PublicPatentCache(Base):
    """
    Global cache for public patent data (abstracts, titles).
    Ensures that if multiple firms fetch the same citation, 
    we only scrape once. No firm-specific data is stored here.
    """
    __tablename__ = "public_patent_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patent_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(Text)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
