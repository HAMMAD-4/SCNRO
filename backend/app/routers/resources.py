"""Resources router — GET /api/v1/resources/available"""

from __future__ import annotations

import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Location, Schedule
from app.services.optimizer import rank_vacant_rooms

router = APIRouter(prefix="/api/v1", tags=["Resources"])

# Optional Redis caching -------------------------------------------------------
try:
    import redis

    _REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _redis_client = redis.from_url(_REDIS_URL, decode_responses=True)
    _redis_client.ping()
    _REDIS_AVAILABLE = True
except Exception:  # pragma: no cover — Redis not required in dev/test
    _REDIS_AVAILABLE = False
    _redis_client = None  # type: ignore[assignment]

_CACHE_TTL = 60  # seconds


def _cache_get(key: str) -> list | None:
    if not _REDIS_AVAILABLE or _redis_client is None:
        return None
    raw = _redis_client.get(key)
    if raw:
        return json.loads(raw)
    return None


def _cache_set(key: str, value: list) -> None:
    if not _REDIS_AVAILABLE or _redis_client is None:
        return
    _redis_client.setex(key, _CACHE_TTL, json.dumps(value, default=str))


# ------------------------------------------------------------------------------


@router.get("/resources/available")
def get_available_resources(
    user_lat: float = Query(31.4826, description="User's current latitude"),
    user_lng: float = Query(74.3036, description="User's current longitude"),
    db: Session = Depends(get_db),
):
    """Return a ranked list of currently vacant classrooms / labs.

    Rooms are considered vacant when no schedule entry covers the current
    day-of-week and time window.  Results are ranked by proximity to the
    user and the length of the remaining free window.
    """
    now = datetime.now()
    current_day = now.isoweekday()  # 1 = Monday … 7 = Sunday
    current_time = now.time()

    cache_key = f"available:{current_day}:{current_time.hour}:{current_time.minute // 5}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return {"available_rooms": cached, "cached": True}

    # Subquery: location_ids that are occupied right now
    occupied_subq = (
        db.query(Schedule.location_id)
        .filter(
            and_(
                Schedule.day_of_week == current_day,
                Schedule.start_time <= current_time,
                Schedule.end_time > current_time,
            )
        )
        .scalar_subquery()
    )

    vacant_locations = (
        db.query(Location)
        .filter(
            Location.is_active == True,  # noqa: E712
            Location.category.in_(["Lab", "Classroom"]),
            ~Location.location_id.in_(occupied_subq),
        )
        .all()
    )

    # For each vacant room, find the next booked slot to compute free window
    rooms_data = []
    for loc in vacant_locations:
        next_schedule = (
            db.query(Schedule)
            .filter(
                Schedule.location_id == loc.location_id,
                Schedule.day_of_week == current_day,
                Schedule.start_time > current_time,
            )
            .order_by(Schedule.start_time)
            .first()
        )
        rooms_data.append(
            {
                "location_id": loc.location_id,
                "name": loc.name,
                "category": loc.category,
                "wing_name": loc.wing_name,
                "floor_level": loc.floor_level,
                "latitude": float(loc.latitude or 0),
                "longitude": float(loc.longitude or 0),
                "free_until": next_schedule.start_time if next_schedule else None,
            }
        )

    ranked = rank_vacant_rooms(rooms_data, user_lat, user_lng)

    # Serialise time objects for JSON / Redis
    for room in ranked:
        if room.get("free_until") is not None:
            room["free_until"] = str(room["free_until"])

    _cache_set(cache_key, ranked)
    return {"available_rooms": ranked, "cached": False}
