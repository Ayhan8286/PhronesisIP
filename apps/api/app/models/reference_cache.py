import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Text, DateTime, Date, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

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
    patent_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    full_description: Mapped[Optional[str]] = mapped_column(Text)
    claims_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=[])
    
    # Status and priority
    priority_date: Mapped[Optional[date]] = mapped_column(Date)
    publication_date: Mapped[Optional[date]] = mapped_column(Date)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
