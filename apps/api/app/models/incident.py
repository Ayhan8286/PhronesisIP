import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base

class SystemIncident(Base):
    """
    Persistent platform-level alerts and outages.
    Visible on the Admin Dashboard to notify developers about system health.
    """
    __tablename__ = "system_incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False) # info, warning, critical
    source: Mapped[str] = mapped_column(String(50), nullable=False) # watchdog, background_job, security
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text)
    
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
