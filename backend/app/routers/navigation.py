"""Navigation router — GET /api/v1/navigate"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database import get_db
from app.models import Location
from app.services.optimizer import get_shortest_path, CAMPUS_GRAPH

router = APIRouter(prefix="/api/v1", tags=["Navigation"])


@router.get("/navigate")
def navigate(
    to: int = Query(..., description="Destination room location_id"),
    from_location: int = Query(1, alias="from", description="Origin location_id (default: Main Entrance)"),
    db: Session = Depends(get_db),
):
    """Return the shortest indoor path from *from_location* to *to*.

    The response includes an ordered list of GPS waypoints that the Flutter
    map layer can render as a polyline.
    """
    destination = db.query(Location).filter(
        Location.location_id == to, Location.is_active == True  # noqa: E712
    ).first()
    if not destination:
        raise HTTPException(status_code=404, detail=f"Location {to} not found or inactive.")

    origin = db.query(Location).filter(
        Location.location_id == from_location, Location.is_active == True  # noqa: E712
    ).first()
    if not origin:
        raise HTTPException(status_code=404, detail=f"Origin location {from_location} not found or inactive.")

    path_data = get_shortest_path(from_location, to)

    return {
        "from": {
            "location_id": origin.location_id,
            "name": origin.name,
            "latitude": str(origin.latitude),
            "longitude": str(origin.longitude),
        },
        "to": {
            "location_id": destination.location_id,
            "name": destination.name,
            "latitude": str(destination.latitude),
            "longitude": str(destination.longitude),
        },
        "path_nodes": path_data["path"],
        "total_distance_m": path_data["total_distance_m"],
        "coordinates": path_data["coordinates"],
    }
