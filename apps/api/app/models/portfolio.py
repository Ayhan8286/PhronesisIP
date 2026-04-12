import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Text, ForeignKey, DateTime, func, Integer, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base

class Client(Base):
    """
    Law firm client (e.g., 'VoiceAI').
    Fulfills 'Attorney selects a client by name' requirement.
    """
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    patents: Mapped[List["Patent"]] = relationship(back_populates="client")
    portfolios: Mapped[List["Portfolio"]] = relationship(back_populates="client")


class Portfolio(Base):
    """
    A specific collection of patents for a due diligence audit.
    Fulfills '2026 Acquisition Audit' groupings.
    """
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_deadline: Mapped[Optional[date]] = mapped_column(Date) # Requirement: 'Attorney can set a report deadline'
    
    # Requirement: 'Previous report retrievable without re-running'
    report_r2_key: Mapped[Optional[str]] = mapped_column(String(500))
    
    status: Mapped[str] = mapped_column(String(50), default="active") # active, archived
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="portfolios")
    patents: Mapped[List["PortfolioPatent"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioPatent(Base):
    """
    Many-to-Many link between Portfolio and Patent with status flags.
    Fulfills 'Attorney can include or exclude specific patents' requirement.
    """
    __tablename__ = "portfolio_patents"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True
    )
    patent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patents.id", ondelete="CASCADE"), primary_key=True
    )
    
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(String(500))
    
    custom_commentary: Mapped[Optional[str]] = mapped_column(Text) # Requirement: 'Attorney can add custom commentary'
    
    # Snapshot of the last DD score
    last_dd_score: Mapped[Optional[int]] = mapped_column(Integer)
    last_dd_finding: Mapped[Optional[str]] = mapped_column(Text)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="patents")
