"""Lost & Found router — POST /api/v1/items/report  |  GET /api/v1/items"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ItemLostFound

router = APIRouter(prefix="/api/v1", tags=["Lost & Found"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ItemReportRequest(BaseModel):
    user_id: int = Field(..., description="ID of the reporting user")
    item_name: str = Field(..., max_length=100)
    description: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=255)
    status: str = Field(..., pattern="^(Lost|Found)$")
    location_last_seen: Optional[int] = Field(None, description="location_id where item was last seen")


class ItemReportResponse(BaseModel):
    item_id: int
    item_name: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/items/report", response_model=ItemReportResponse, status_code=201)
def report_item(payload: ItemReportRequest, db: Session = Depends(get_db)):
    """Report a lost or found item on the community board."""
    item = ItemLostFound(
        user_id=payload.user_id,
        item_name=payload.item_name,
        description=payload.description,
        image_url=payload.image_url,
        status=payload.status,
        location_last_seen=payload.location_last_seen,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/items")
def list_items(
    status: Optional[str] = Query(None, description="Filter by status: Lost, Found, Claimed"),
    db: Session = Depends(get_db),
):
    """List all lost & found items, optionally filtered by status."""
    query = db.query(ItemLostFound)
    if status:
        if status not in ("Lost", "Found", "Claimed"):
            raise HTTPException(status_code=400, detail="status must be one of: Lost, Found, Claimed")
        query = query.filter(ItemLostFound.status == status)

    items = query.order_by(ItemLostFound.created_at.desc()).all()
    return {
        "items": [
            {
                "item_id": i.item_id,
                "user_id": i.user_id,
                "item_name": i.item_name,
                "description": i.description,
                "image_url": i.image_url,
                "status": i.status,
                "location_last_seen": i.location_last_seen,
                "created_at": str(i.created_at),
            }
            for i in items
        ]
    }


@router.patch("/items/{item_id}/claim")
def claim_item(item_id: int, db: Session = Depends(get_db)):
    """Mark an item as claimed."""
    item = db.query(ItemLostFound).filter(ItemLostFound.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")
    item.status = "Claimed"
    db.commit()
    db.refresh(item)
    return {"item_id": item.item_id, "status": item.status}
