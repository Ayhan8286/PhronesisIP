import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class ServiceOrder(Base):
    """
    Tracks external service requests (Prior Art Search, Patentability, etc.)
    from the public intake form.
    """
    __tablename__ = "service_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_email = Column(String(255), nullable=False)
    client_name = Column(String(255), nullable=True)
    
    service_package = Column(String(100), nullable=False) # prior_art, patentability, office_action
    
    # Input data
    description = Column(Text, nullable=True)
    uploaded_file_key = Column(String(512), nullable=True) # R2 key for office action or invention doc
    
    # Metadata
    status = Column(String(50), default="pending") # pending, paid, in_progress, completed
    stripe_session_id = Column(String(255), nullable=True)
    
    # Results
    report_file_key = Column(String(512), nullable=True) # R2 key for the final branded PDF
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ServiceOrder(id={self.id}, email={self.client_email}, package={self.service_package})>"
