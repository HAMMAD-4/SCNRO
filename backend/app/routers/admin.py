"""Admin router — manage signup requests, staff (users + faculty), lost&found closure."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth_utils import hash_password, require_role
from app.database import get_db
from app.models import Faculty, ItemLostFound, Location, SignupRequest, User, Course, Enrollment

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])
_admin = Depends(require_role("admin"))


# ── Schemas ─────────────────────────────────────────────────────────────────

class StaffCreateRequest(BaseModel):
    email: str
    name: str
    password: str = Field(..., min_length=6)
    role: str = Field(..., description="teacher | student | sac | head_clerk | admin")
    designation: Optional[str] = None
    department: Optional[str] = None
    office_location_id: Optional[int] = None


class StaffUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    office_location_id: Optional[int] = None
    is_available: Optional[bool] = None


class FacultyUpdateRequest(BaseModel):
    name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    office_location_id: Optional[int] = None
    is_available: Optional[bool] = None


# ── Signup Requests ──────────────────────────────────────────────────────────

@router.get("/signup-requests")
def list_signup_requests(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """List all signup requests, optionally filtered by status."""
    q = db.query(SignupRequest)
    if status:
        q = q.filter(SignupRequest.status == status)
    requests = q.order_by(SignupRequest.created_at.desc()).all()
    return {
        "requests": [
            {
                "request_id": r.request_id,
                "email": r.email,
                "name": r.name,
                "role_requested": r.role_requested,
                "status": r.status,
                "created_at": str(r.created_at),
            }
            for r in requests
        ]
    }


@router.post("/signup-requests/{request_id}/approve")
def approve_signup(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Approve a pending signup request — creates the user account."""
    req = db.query(SignupRequest).filter(
        SignupRequest.request_id == request_id,
        SignupRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found.")

    # Guard against race-condition duplicate
    if db.query(User).filter(User.email == req.email).first():
        req.status = "rejected"
        db.commit()
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = User(
        email=req.email,
        name=req.name,
        password_hash=req.password_hash,
        role=req.role_requested,
        is_active=True,
    )
    db.add(user)
    req.status = "approved"
    db.commit()
    db.refresh(user)
    return {"message": "Approved.", "user_id": user.user_id, "email": user.email}


@router.post("/signup-requests/{request_id}/reject")
def reject_signup(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Reject a pending signup request."""
    req = db.query(SignupRequest).filter(
        SignupRequest.request_id == request_id,
        SignupRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found.")
    req.status = "rejected"
    db.commit()
    return {"message": "Rejected.", "request_id": request_id}


# ── Staff (User) Management ──────────────────────────────────────────────────

@router.get("/staff")
def list_staff(
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """List all portal users (staff), optionally filtered by role."""
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    users = q.order_by(User.name).all()
    return {
        "staff": [
            {
                "user_id": u.user_id,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": str(u.created_at),
            }
            for u in users
        ]
    }


@router.post("/staff", status_code=201)
def create_staff(
    payload: StaffCreateRequest,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Create a new portal user (admin-initiated, no approval required)."""
    email = payload.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = User(
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()  # get user_id before commit

    # Optionally create a faculty directory entry for teachers
    if payload.role == "teacher":
        fac = Faculty(
            name=payload.name,
            designation=payload.designation,
            department=payload.department,
            office_location_id=payload.office_location_id,
            is_available=True,
        )
        db.add(fac)

    db.commit()
    db.refresh(user)
    return {"message": "Created.", "user_id": user.user_id, "email": user.email}


@router.put("/staff/{user_id}")
def update_staff(
    user_id: int,
    payload: StaffUpdateRequest,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Update an existing portal user's details."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = payload.email.lower().strip()
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return {"message": "Updated.", "user_id": user.user_id}


@router.delete("/staff/{user_id}")
def delete_staff(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Deactivate (soft-delete) a portal user."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = False
    db.commit()
    return {"message": "User deactivated.", "user_id": user_id}


# ── Faculty Directory Management ─────────────────────────────────────────────

@router.get("/faculty")
def list_faculty_admin(db: Session = Depends(get_db), _: User = _admin):
    """List all faculty directory entries."""
    faculty = db.query(Faculty).all()
    return {
        "faculty": [
            {
                "faculty_id": f.faculty_id,
                "name": f.name,
                "designation": f.designation,
                "department": f.department,
                "office_location_id": f.office_location_id,
                "is_available": f.is_available,
            }
            for f in faculty
        ]
    }


@router.post("/faculty", status_code=201)
def create_faculty(
    payload: FacultyUpdateRequest,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Add a faculty member to the campus directory."""
    fac = Faculty(
        name=payload.name or "",
        designation=payload.designation,
        department=payload.department,
        office_location_id=payload.office_location_id,
        is_available=payload.is_available if payload.is_available is not None else True,
    )
    db.add(fac)
    db.commit()
    db.refresh(fac)
    return {"message": "Created.", "faculty_id": fac.faculty_id}


@router.put("/faculty/{faculty_id}")
def update_faculty(
    faculty_id: int,
    payload: FacultyUpdateRequest,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Update a faculty directory entry."""
    fac = db.query(Faculty).filter(Faculty.faculty_id == faculty_id).first()
    if not fac:
        raise HTTPException(status_code=404, detail="Faculty not found.")

    if payload.name is not None:
        fac.name = payload.name
    if payload.designation is not None:
        fac.designation = payload.designation
    if payload.department is not None:
        fac.department = payload.department
    if payload.office_location_id is not None:
        fac.office_location_id = payload.office_location_id
    if payload.is_available is not None:
        fac.is_available = payload.is_available

    db.commit()
    return {"message": "Updated.", "faculty_id": faculty_id}


@router.delete("/faculty/{faculty_id}")
def delete_faculty(
    faculty_id: int,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Remove a faculty member from the campus directory."""
    fac = db.query(Faculty).filter(Faculty.faculty_id == faculty_id).first()
    if not fac:
        raise HTTPException(status_code=404, detail="Faculty not found.")
    db.delete(fac)
    db.commit()
    return {"message": "Deleted.", "faculty_id": faculty_id}


# ── Unlock a finalized mark category ─────────────────────────────────────────

@router.post("/marks/unlock")
def unlock_category(
    course_id: int,
    category: str,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Admin-only: unlock a finalized mark category so the teacher can edit again."""
    from app.models import CategoryLock

    lock = db.query(CategoryLock).filter(
        CategoryLock.course_id == course_id,
        CategoryLock.category == category,
    ).first()
    if not lock:
        raise HTTPException(status_code=404, detail="No lock found for this course/category.")
    lock.is_locked = False
    db.commit()
    return {"message": f"Category '{category}' unlocked for course {course_id}."}


# ── Lost & Found Closure ─────────────────────────────────────────────────────

@router.patch("/lost-found/{item_id}/close")
def close_lost_found(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "sac")),
):
    """Mark a lost & found report as Closed (SAC office or admin only)."""
    item = db.query(ItemLostFound).filter(ItemLostFound.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")
    if item.status == "Closed":
        raise HTTPException(status_code=400, detail="Item already closed.")
    item.status = "Closed"
    item.closed_by = current_user.user_id
    db.commit()
    return {"item_id": item.item_id, "status": item.status}


# ── Mark Change Requests ─────────────────────────────────────────────────────

@router.post("/mark-change-requests/{request_id}/accept")
def accept_mark_change_request(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Accept a teacher's mark change request and auto-update the mark."""
    from datetime import datetime, timezone

    from app.models import MarkChangeRequest, MarkRecord

    req = db.query(MarkChangeRequest).filter(
        MarkChangeRequest.request_id == request_id,
        MarkChangeRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found.")

    record = db.query(MarkRecord).filter(MarkRecord.record_id == req.record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mark record not found.")

    record.marks_obtained = req.new_marks_obtained
    if req.new_total_marks is not None:
        record.total_marks = req.new_total_marks
    req.status = "accepted"
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Request accepted and marks updated.", "request_id": request_id}


@router.post("/mark-change-requests/{request_id}/reject")
def reject_mark_change_request(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Reject a teacher's mark change request."""
    from datetime import datetime, timezone

    from app.models import MarkChangeRequest

    req = db.query(MarkChangeRequest).filter(
        MarkChangeRequest.request_id == request_id,
        MarkChangeRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found.")
    req.status = "rejected"
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Request rejected.", "request_id": request_id}


# ── Course Requests (head_clerk submits, admin approves) ──────────────────────

@router.get("/course-requests")
def list_course_requests(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """List all course registration requests."""
    from app.models import CourseRequest

    q = db.query(CourseRequest)
    if status:
        q = q.filter(CourseRequest.status == status)
    reqs = q.order_by(CourseRequest.created_at.desc()).all()
    result = []
    for r in reqs:
        clerk   = db.query(User).filter(User.user_id == r.clerk_id).first()
        teacher = db.query(User).filter(User.user_id == r.teacher_id).first()
        result.append({
            "request_id":  r.request_id,
            "code":        r.code,
            "name":        r.name,
            "section":     r.section,
            "semester":    r.semester,
            "teacher_name": teacher.name if teacher else "?",
            "teacher_id":  r.teacher_id,
            "clerk_name":  clerk.name if clerk else "?",
            "status":      r.status,
            "created_at":  str(r.created_at),
        })
    return {"requests": result}


@router.post("/course-requests/{request_id}/approve")
def approve_course_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = _admin,
):
    """Approve a pending course request — creates the course."""
    from datetime import datetime, timezone

    from app.models import CourseRequest

    req = db.query(CourseRequest).filter(
        CourseRequest.request_id == request_id,
        CourseRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found.")

    course = Course(
        code=req.code,
        name=req.name,
        teacher_id=req.teacher_id,
        section=req.section,
        semester=req.semester,
        is_active=True,
    )
    db.add(course)
    req.status = "approved"
    req.reviewed_by = current_user.user_id if not isinstance(current_user, type) else None
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(course)
    return {"message": "Course created.", "course_id": course.course_id}


@router.post("/course-requests/{request_id}/reject")
def reject_course_request(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Reject a pending course request."""
    from datetime import datetime, timezone

    from app.models import CourseRequest

    req = db.query(CourseRequest).filter(
        CourseRequest.request_id == request_id,
        CourseRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found.")
    req.status = "rejected"
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Rejected.", "request_id": request_id}


# ── Enrollment Requests (student submits, admin approves) ─────────────────────

@router.get("/enrollment-requests")
def list_enrollment_requests(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """List all student enrollment requests."""
    from app.models import EnrollmentRequest

    q = db.query(EnrollmentRequest)
    if status:
        q = q.filter(EnrollmentRequest.status == status)
    reqs = q.order_by(EnrollmentRequest.created_at.desc()).all()
    result = []
    for r in reqs:
        student = db.query(User).filter(User.user_id == r.student_id).first()
        course  = db.query(Course).filter(Course.course_id == r.course_id).first()
        teacher = db.query(User).filter(User.user_id == course.teacher_id).first() if course else None
        result.append({
            "request_id":   r.request_id,
            "student_name": student.name if student else "?",
            "student_email": student.email if student else "?",
            "course_code":  course.code if course else "?",
            "course_name":  course.name if course else "?",
            "teacher_name": teacher.name if teacher else "?",
            "status":       r.status,
            "created_at":   str(r.created_at),
        })
    return {"requests": result}


@router.post("/enrollment-requests/{request_id}/approve")
def approve_enrollment_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = _admin,
):
    """Approve a student enrollment request — creates the Enrollment."""
    from datetime import datetime, timezone

    from app.models import EnrollmentRequest

    req = db.query(EnrollmentRequest).filter(
        EnrollmentRequest.request_id == request_id,
        EnrollmentRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found.")

    # Check not already enrolled
    existing = db.query(Enrollment).filter(
        Enrollment.student_id == req.student_id,
        Enrollment.course_id  == req.course_id,
    ).first()
    if existing:
        req.status = "approved"
        db.commit()
        return {"message": "Already enrolled (marked approved).", "enrollment_id": existing.enrollment_id}

    enroll = Enrollment(student_id=req.student_id, course_id=req.course_id)
    db.add(enroll)
    req.status = "approved"
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(enroll)
    return {"message": "Enrollment created.", "enrollment_id": enroll.enrollment_id}


@router.post("/enrollment-requests/{request_id}/reject")
def reject_enrollment_request(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Reject a student enrollment request."""
    from datetime import datetime, timezone

    from app.models import EnrollmentRequest

    req = db.query(EnrollmentRequest).filter(
        EnrollmentRequest.request_id == request_id,
        EnrollmentRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found.")
    req.status = "rejected"
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Rejected.", "request_id": request_id}


# ── Reactivate user ──────────────────────────────────────────────────────────

@router.post("/staff/{user_id}/reactivate")
def reactivate_staff(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = _admin,
):
    """Re-activate a previously deactivated user account."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = True
    db.commit()
    return {"message": "User reactivated.", "user_id": user_id}
