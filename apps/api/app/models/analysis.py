import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, ForeignKey, DateTime, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base

class AnalysisWorkflow(Base):
    """
    State tracking for a specific legal analysis (Infringement/Invalidity).
    Fulfills 'Analysis ID in URL — Firm B attorney must get 404' and 
    'Workflow record' requirements.
    """
    __tablename__ = "analysis_workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    patent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patents.id"), nullable=False
    )
    
    analysis_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # infringement, invalidity, fto
    
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, running, completed, error
    
    # Storage for the final DOCX report in R2
    report_r2_key: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Forensic Cost Tracking (Requirement: 'Cost per analysis logged')
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Privilege & Compliance (Requirement: 'Marked as attorney work product')
    is_work_product: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    product_descriptions: Mapped[List["ProductDescription"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")
    claim_results: Mapped[List["ClaimAnalysisResult"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")


class ProductDescription(Base):
    """
    Stored product technical details.
    Fulfills 'Product description saved to workflow record' requirement.
    """
    __tablename__ = "product_descriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_workflows.id", ondelete="CASCADE"), nullable=False
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False
    )
    
    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workflow: Mapped["AnalysisWorkflow"] = relationship(back_populates="product_descriptions")


class ClaimAnalysisResult(Base):
    """
    Element-by-element analysis results per claim.
    Fulfills 'Element-by-element mapping' and 'Risk level assigned per claim' requirements.
    """
    __tablename__ = "claim_analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_workflows.id", ondelete="CASCADE"), nullable=False
    )
    
    claim_number: Mapped[int] = mapped_column(nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Structured JSON Mapping: [{"element": "...", "product_feature": "...", "status": "yes/no/partial", "notes": "..."}]
    element_mappings: Mapped[dict] = mapped_column(JSONB, default=[])
    
    risk_level: Mapped[str] = mapped_column(String(20)) # High, Medium, Low
    risk_score: Mapped[int] = mapped_column(default=0)
    
    non_infringement_arguments: Mapped[Optional[str]] = mapped_column(Text)
    
    # Requirement: 'No legal conclusions' - We store AI findings separately from Final Attorney Review
    ai_finding: Mapped[str] = mapped_column(Text)
    attorney_notes: Mapped[Optional[str]] = mapped_column(Text)

    workflow: Mapped["AnalysisWorkflow"] = relationship(back_populates="claim_results")
