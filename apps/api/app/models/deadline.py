import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Date, DateTime, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base

class PatentDeadline(Base):
    """
    Automated and manual deadlines for patent maintenance and prosecution.
    """
    __tablename__ = "patent_deadlines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Type: MAINTENANCE_FEE, OA_RESPONSE, PCT_NATIONAL_PHASE, RENEWAL
    deadline_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    description: Mapped[Optional[str]] = mapped_column(String(500))
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Status: PENDING, COMPLETED, OVERDUE, DISMISSED
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Tracking for alert triggers (90, 60, 30 days)
    alert_flags: Mapped[int] = mapped_column(Integer, default=0) # Bitmask or count of alerts sent
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    patent: Mapped["Patent"] = relationship(back_populates="deadlines")
