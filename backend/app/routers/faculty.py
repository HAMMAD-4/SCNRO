"""Faculty router — GET /api/v1/faculty/search"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Faculty, Location

router = APIRouter(prefix="/api/v1", tags=["Faculty"])


@router.get("/faculty/search")
def search_faculty(
    name: str = Query(..., min_length=1, description="Full or partial faculty name"),
    db: Session = Depends(get_db),
):
    """Search for faculty members by name.

    Returns the office location details and current availability for each
    matching faculty member so the Flutter app can display a 'Navigate to
    Office' button.
    """
    results = (
        db.query(Faculty)
        .filter(Faculty.name.ilike(f"%{name}%"))
        .all()
    )

    if not results:
        return {"faculty": []}

    response = []
    for f in results:
        office: Optional[Location] = (
            db.query(Location).filter(Location.location_id == f.office_location_id).first()
            if f.office_location_id
            else None
        )
        response.append(
            {
                "faculty_id": f.faculty_id,
                "name": f.name,
                "designation": f.designation,
                "department": f.department,
                "is_available": f.is_available,
                "office": {
                    "location_id": office.location_id if office else None,
                    "name": office.name if office else None,
                    "wing_name": office.wing_name if office else None,
                    "floor_level": office.floor_level if office else None,
                    "latitude": str(office.latitude) if office and office.latitude else None,
                    "longitude": str(office.longitude) if office and office.longitude else None,
                }
                if office
                else None,
            }
        )

    return {"faculty": response}


@router.get("/faculty/{faculty_id}")
def get_faculty(faculty_id: int, db: Session = Depends(get_db)):
    """Get a single faculty member's details by ID."""
    faculty_member = db.query(Faculty).filter(Faculty.faculty_id == faculty_id).first()
    if not faculty_member:
        raise HTTPException(status_code=404, detail="Faculty member not found.")

    office = (
        db.query(Location).filter(Location.location_id == faculty_member.office_location_id).first()
        if faculty_member.office_location_id
        else None
    )

    return {
        "faculty_id": faculty_member.faculty_id,
        "name": faculty_member.name,
        "designation": faculty_member.designation,
        "department": faculty_member.department,
        "is_available": faculty_member.is_available,
        "office": {
            "location_id": office.location_id,
            "name": office.name,
            "wing_name": office.wing_name,
            "floor_level": office.floor_level,
            "latitude": str(office.latitude) if office.latitude else None,
            "longitude": str(office.longitude) if office.longitude else None,
        }
        if office
        else None,
    }
