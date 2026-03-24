"""Clerk router — head-clerk manages room schedules and location availability."""

from __future__ import annotations

from datetime import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_utils import get_current_user, require_role
from app.database import get_db
from app.models import Location, Schedule, User

router = APIRouter(prefix="/api/v1/clerk", tags=["Room Management"])

# head_clerk manages rooms; admin can also access
_clerk_or_admin = Depends(require_role("head_clerk", "admin"))


# ── Schemas ──────────────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    location_id: int
    course_code: str
    day_of_week: int  # 1 Mon – 7 Sun
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"
    section: Optional[str] = None
    notes: Optional[str] = None


class ScheduleUpdate(BaseModel):
    location_id: Optional[int] = None
    course_code: Optional[str] = None
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    section: Optional[str] = None
    notes: Optional[str] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    wing_name: Optional[str] = None
    floor_level: Optional[int] = None
    is_active: Optional[bool] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_time(s: str) -> time:
    try:
        h, m = s.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid time format '{s}'. Use HH:MM.")


DAY_NAMES = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}


def _schedule_dict(s: Schedule, location_name: Optional[str] = None) -> dict:
    return {
        "schedule_id": s.schedule_id,
        "location_id": s.location_id,
        "location_name": location_name,
        "course_code": s.course_code,
        "day_of_week": s.day_of_week,
        "day_name": DAY_NAMES.get(s.day_of_week, "?"),
        "start_time": str(s.start_time) if s.start_time else None,
        "end_time": str(s.end_time) if s.end_time else None,
        "section": s.section,
        "notes": s.notes,
    }


# ── Schedule CRUD ─────────────────────────────────────────────────────────────

@router.get("/schedules")
def list_schedules(
    location_id: Optional[int] = None,
    day_of_week: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """List all schedules, optionally filtered by location and/or day."""
    q = db.query(Schedule)
    if location_id:
        q = q.filter(Schedule.location_id == location_id)
    if day_of_week:
        q = q.filter(Schedule.day_of_week == day_of_week)
    schedules = q.order_by(Schedule.day_of_week, Schedule.start_time).all()

    loc_map = {
        loc.location_id: loc.name
        for loc in db.query(Location).all()
    }
    return {
        "schedules": [
            _schedule_dict(s, loc_map.get(s.location_id))
            for s in schedules
        ]
    }


@router.post("/schedules", status_code=201)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Add a new room booking / lecture slot."""
    loc = db.query(Location).filter(Location.location_id == payload.location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found.")

    sched = Schedule(
        location_id=payload.location_id,
        course_code=payload.course_code,
        day_of_week=payload.day_of_week,
        start_time=_parse_time(payload.start_time),
        end_time=_parse_time(payload.end_time),
        section=payload.section,
        notes=payload.notes,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return {"message": "Schedule created.", "schedule_id": sched.schedule_id}


@router.put("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Update an existing schedule entry."""
    sched = db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found.")

    if payload.location_id is not None:
        loc = db.query(Location).filter(Location.location_id == payload.location_id).first()
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found.")
        sched.location_id = payload.location_id
    if payload.course_code is not None:
        sched.course_code = payload.course_code
    if payload.day_of_week is not None:
        sched.day_of_week = payload.day_of_week
    if payload.start_time is not None:
        sched.start_time = _parse_time(payload.start_time)
    if payload.end_time is not None:
        sched.end_time = _parse_time(payload.end_time)
    if payload.section is not None:
        sched.section = payload.section
    if payload.notes is not None:
        sched.notes = payload.notes

    db.commit()
    return {"message": "Schedule updated.", "schedule_id": schedule_id}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Delete a schedule entry."""
    sched = db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    db.delete(sched)
    db.commit()
    return {"message": "Schedule deleted."}


# ── Location availability ─────────────────────────────────────────────────────

@router.get("/locations")
def list_locations(
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """List all campus locations with availability status."""
    locations = db.query(Location).order_by(Location.name).all()
    return {
        "locations": [
            {
                "location_id": loc.location_id,
                "name": loc.name,
                "category": loc.category,
                "wing_name": loc.wing_name,
                "floor_level": loc.floor_level,
                "is_active": loc.is_active,
            }
            for loc in locations
        ]
    }


@router.put("/locations/{location_id}")
def update_location(
    location_id: int,
    payload: LocationUpdate,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Update a location's details or toggle its availability."""
    loc = db.query(Location).filter(Location.location_id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found.")

    if payload.name is not None:
        loc.name = payload.name
    if payload.category is not None:
        loc.category = payload.category
    if payload.wing_name is not None:
        loc.wing_name = payload.wing_name
    if payload.floor_level is not None:
        loc.floor_level = payload.floor_level
    if payload.is_active is not None:
        loc.is_active = payload.is_active

    db.commit()
    return {"message": "Location updated.", "location_id": location_id}
