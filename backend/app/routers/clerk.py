"""Clerk router — head-clerk manages room schedules, locations, sections, and course requests."""

from __future__ import annotations

from datetime import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_utils import get_current_user, require_role
from app.database import get_db
from app.models import Location, Schedule, Section, StudentSection, User

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


class LocationCreate(BaseModel):
    name: str
    category: Optional[str] = None
    wing_name: Optional[str] = None
    floor_level: Optional[int] = None
    is_active: bool = True


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


@router.post("/locations", status_code=201)
def create_location(
    payload: LocationCreate,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Create a new campus room / location."""
    loc = Location(
        name=payload.name,
        category=payload.category,
        wing_name=payload.wing_name,
        floor_level=payload.floor_level,
        is_active=payload.is_active,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return {
        "message": "Location created.",
        "location_id": loc.location_id,
        "name": loc.name,
    }


@router.delete("/locations/{location_id}")
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Delete a campus location.

    Schedules referencing this location are also deleted to preserve integrity.
    """
    loc = db.query(Location).filter(Location.location_id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found.")

    # Remove schedules referencing this location first
    db.query(Schedule).filter(Schedule.location_id == location_id).delete()
    db.delete(loc)
    db.commit()
    return {"message": "Location deleted.", "location_id": location_id}


# ── Course Requests ───────────────────────────────────────────────────────────

class CourseRequestCreate(BaseModel):
    code: str
    name: str
    teacher_id: int
    section: Optional[str] = None
    section_id: Optional[int] = None   # Section object for auto-enrollment
    semester: Optional[str] = None


@router.post("/course-requests", status_code=201)
def submit_course_request(
    payload: CourseRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = _clerk_or_admin,
):
    """Head clerk submits a course registration request for admin approval."""
    from app.models import CourseRequest

    teacher = db.query(User).filter(
        User.user_id == payload.teacher_id,
        User.role == "teacher",
    ).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    # Validate section object if provided
    sec_name = payload.section
    if payload.section_id:
        sec = db.query(Section).filter(Section.section_id == payload.section_id).first()
        if not sec:
            raise HTTPException(status_code=404, detail="Section not found.")
        sec_name = sec_name or sec.name

    req = CourseRequest(
        clerk_id=current_user.user_id,
        code=payload.code,
        name=payload.name,
        teacher_id=payload.teacher_id,
        section=sec_name,
        section_id=payload.section_id,
        semester=payload.semester,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {"message": "Course request submitted.", "request_id": req.request_id}


@router.get("/course-requests")
def list_my_course_requests(
    db: Session = Depends(get_db),
    current_user: User = _clerk_or_admin,
):
    """List course requests submitted by this clerk (or all if admin)."""
    from app.models import CourseRequest

    q = db.query(CourseRequest)
    if current_user.role != "admin":
        q = q.filter(CourseRequest.clerk_id == current_user.user_id)
    reqs = q.order_by(CourseRequest.created_at.desc()).all()
    result = []
    for r in reqs:
        teacher = db.query(User).filter(User.user_id == r.teacher_id).first()
        result.append({
            "request_id": r.request_id,
            "code": r.code,
            "name": r.name,
            "section": r.section,
            "semester": r.semester,
            "teacher_name": teacher.name if teacher else "?",
            "status": r.status,
            "created_at": str(r.created_at),
        })
    return {"requests": result}


# ── Section Management ────────────────────────────────────────────────────────

VALID_PROGRAMS = {"IT", "SE", "CS", "DS", "AI"}


@router.get("/teachers")
def list_teachers(
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Return active teachers, optionally filtered by department."""
    q = db.query(User).filter(User.role == "teacher", User.is_active.is_(True))
    if department:
        q = q.filter(User.department == department)
    teachers = q.order_by(User.name).all()
    return {
        "teachers": [
            {"user_id": t.user_id, "name": t.name, "email": t.email, "department": t.department}
            for t in teachers
        ]
    }


@router.get("/degree-coordinators")
def list_degree_coordinators(
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Return active degree coordinators, optionally filtered by department."""
    q = db.query(User).filter(User.role == "degree_coordinator", User.is_active.is_(True))
    if department:
        q = q.filter(User.department == department)
    dcs = q.order_by(User.name).all()
    return {
        "coordinators": [
            {"user_id": d.user_id, "name": d.name, "email": d.email, "department": d.department}
            for d in dcs
        ]
    }


@router.get("/students")
def list_students(
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Return active students, optionally filtered by department."""
    q = db.query(User).filter(User.role == "student", User.is_active.is_(True))
    if department:
        q = q.filter(User.department == department)
    students = q.order_by(User.name).all()
    return {
        "students": [
            {"user_id": s.user_id, "name": s.name, "email": s.email, "department": s.department}
            for s in students
        ]
    }


class SectionCreate(BaseModel):
    name: str
    program: str
    semester: Optional[str] = None
    coordinator_id: Optional[int] = None


class SectionUpdate(BaseModel):
    name: Optional[str] = None
    program: Optional[str] = None
    semester: Optional[str] = None
    coordinator_id: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/sections")
def list_sections(
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """List all sections."""
    sections = db.query(Section).order_by(Section.program, Section.name).all()
    result = []
    for s in sections:
        coord = db.query(User).filter(User.user_id == s.coordinator_id).first() if s.coordinator_id else None
        student_count = db.query(StudentSection).filter(StudentSection.section_id == s.section_id).count()
        result.append({
            "section_id": s.section_id,
            "name": s.name,
            "program": s.program,
            "semester": s.semester,
            "coordinator_name": coord.name if coord else None,
            "coordinator_id": s.coordinator_id,
            "is_active": s.is_active,
            "student_count": student_count,
        })
    return {"sections": result}


@router.post("/sections", status_code=201)
def create_section(
    payload: SectionCreate,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Create a new academic section."""
    if payload.program not in VALID_PROGRAMS:
        raise HTTPException(status_code=400, detail=f"program must be one of: {', '.join(VALID_PROGRAMS)}")

    if payload.coordinator_id:
        coord = db.query(User).filter(
            User.user_id == payload.coordinator_id,
            User.role == "degree_coordinator",
        ).first()
        if not coord:
            raise HTTPException(status_code=404, detail="Degree coordinator not found.")

    sec = Section(
        name=payload.name,
        program=payload.program,
        semester=payload.semester,
        coordinator_id=payload.coordinator_id,
    )
    db.add(sec)
    db.commit()
    db.refresh(sec)
    return {"message": "Section created.", "section_id": sec.section_id}


@router.put("/sections/{section_id}")
def update_section(
    section_id: int,
    payload: SectionUpdate,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Update a section."""
    sec = db.query(Section).filter(Section.section_id == section_id).first()
    if not sec:
        raise HTTPException(status_code=404, detail="Section not found.")

    if payload.program is not None:
        if payload.program not in VALID_PROGRAMS:
            raise HTTPException(status_code=400, detail=f"program must be one of: {', '.join(VALID_PROGRAMS)}")
        sec.program = payload.program
    if payload.name is not None:
        sec.name = payload.name
    if payload.semester is not None:
        sec.semester = payload.semester
    if payload.coordinator_id is not None:
        coord = db.query(User).filter(
            User.user_id == payload.coordinator_id,
            User.role.in_(["degree_coordinator", "admin"]),
        ).first()
        if not coord:
            raise HTTPException(status_code=404, detail="Coordinator not found.")
        sec.coordinator_id = payload.coordinator_id
    if payload.is_active is not None:
        sec.is_active = payload.is_active

    db.commit()
    return {"message": "Section updated.", "section_id": section_id}


@router.delete("/sections/{section_id}")
def delete_section(
    section_id: int,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Delete a section and its student memberships."""
    sec = db.query(Section).filter(Section.section_id == section_id).first()
    if not sec:
        raise HTTPException(status_code=404, detail="Section not found.")
    db.query(StudentSection).filter(StudentSection.section_id == section_id).delete()
    db.delete(sec)
    db.commit()
    return {"message": "Section deleted.", "section_id": section_id}


@router.get("/sections/{section_id}/students")
def list_section_students(
    section_id: int,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """List students enrolled in a section."""
    sec = db.query(Section).filter(Section.section_id == section_id).first()
    if not sec:
        raise HTTPException(status_code=404, detail="Section not found.")

    student_sections = db.query(StudentSection).filter(
        StudentSection.section_id == section_id
    ).all()
    result = []
    for ss in student_sections:
        u = db.query(User).filter(User.user_id == ss.student_id).first()
        if u:
            result.append({
                "student_id": u.user_id,
                "name": u.name,
                "email": u.email,
                "enrolled_at": str(ss.enrolled_at),
            })
    return {"students": result, "section_id": section_id, "section_name": sec.name}


class StudentEnrollRequest(BaseModel):
    student_id: int


@router.post("/sections/{section_id}/students", status_code=201)
def add_student_to_section(
    section_id: int,
    payload: StudentEnrollRequest,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Assign a student to a section."""
    sec = db.query(Section).filter(Section.section_id == section_id).first()
    if not sec:
        raise HTTPException(status_code=404, detail="Section not found.")

    student = db.query(User).filter(
        User.user_id == payload.student_id, User.role == "student"
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    existing = db.query(StudentSection).filter(
        StudentSection.student_id == payload.student_id,
        StudentSection.section_id == section_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Student already in this section.")

    ss = StudentSection(student_id=payload.student_id, section_id=section_id)
    db.add(ss)
    db.commit()
    return {"message": "Student added to section.", "student_id": payload.student_id, "section_id": section_id}


@router.delete("/sections/{section_id}/students/{student_id}")
def remove_student_from_section(
    section_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    _: User = _clerk_or_admin,
):
    """Remove a student from a section."""
    ss = db.query(StudentSection).filter(
        StudentSection.section_id == section_id,
        StudentSection.student_id == student_id,
    ).first()
    if not ss:
        raise HTTPException(status_code=404, detail="Student not found in section.")
    db.delete(ss)
    db.commit()
    return {"message": "Student removed from section."}
