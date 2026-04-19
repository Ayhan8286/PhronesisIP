from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.service_order import ServiceOrder
from app.schemas.service_order import ServiceOrderCreate, ServiceOrderResponse
import uuid

router = APIRouter()

@router.post("/intake", response_model=ServiceOrderResponse, status_code=status.HTTP_201_CREATED)
async def public_intake(
    data: ServiceOrderCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for service intake. 
    Does not require authentication to allow high-friction-less lead generation.
    """
    order = ServiceOrder(
        id=uuid.uuid4(),
        client_email=data.client_email,
        client_name=data.client_name,
        service_package=data.service_package,
        description=data.description,
        uploaded_file_key=data.uploaded_file_key,
        status="pending"
    )
    
    db.add(order)
    await db.commit()
    await db.refresh(order)
    
    # In a production app, this would trigger an email notification to the admin/user
    return order

@router.get("/status/{order_id}", response_model=ServiceOrderResponse)
async def get_order_status(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Check status of a service order by UUID."""
    order = await db.get(ServiceOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
