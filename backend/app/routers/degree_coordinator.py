"""Degree Coordinator router — view section, students, schedule, approve enrollment requests."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_utils import get_current_user, require_role
from app.database import get_db
from app.models import (
    Course, Enrollment, EnrollmentRequest, MarkRecord, Schedule,
    Section, StudentSection, User, CategoryLock,
)

router = APIRouter(prefix="/api/v1/dc", tags=["Degree Coordinator"])

_dc_or_admin = Depends(require_role("degree_coordinator", "admin"))


def _get_dc_section(current_user: User, db: Session) -> Section:
    """Return the section for which the current user is the coordinator."""
    section = db.query(Section).filter(
        Section.coordinator_id == current_user.user_id,
        Section.is_active.is_(True),
    ).first()
    if not section:
        raise HTTPException(status_code=404, detail="No section assigned to this coordinator.")
    return section


# ── Section info ──────────────────────────────────────────────────────────────

@router.get("/my-section")
def get_my_section(
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """Get the coordinator's section details."""
    if current_user.role == "admin":
        # Admin can pass section_id query param to view any section
        sections = db.query(Section).filter(Section.is_active.is_(True)).all()
        return {
            "sections": [
                {
                    "section_id": s.section_id,
                    "name": s.name,
                    "program": s.program,
                    "semester": s.semester,
                    "coordinator_name": db.query(User).filter(
                        User.user_id == s.coordinator_id).first().name
                    if s.coordinator_id else None,
                    "student_count": db.query(StudentSection).filter(
                        StudentSection.section_id == s.section_id).count(),
                }
                for s in sections
            ]
        }
    section = _get_dc_section(current_user, db)
    student_count = db.query(StudentSection).filter(
        StudentSection.section_id == section.section_id
    ).count()
    return {
        "section_id": section.section_id,
        "name": section.name,
        "program": section.program,
        "semester": section.semester,
        "student_count": student_count,
    }


# ── Students in section ───────────────────────────────────────────────────────

@router.get("/students")
def get_section_students(
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """List all students in the coordinator's section."""
    if current_user.role == "degree_coordinator":
        section = _get_dc_section(current_user, db)
        sid = section.section_id
    else:
        if not section_id:
            raise HTTPException(status_code=400, detail="section_id required for admin.")
        sid = section_id

    student_sections = db.query(StudentSection).filter(
        StudentSection.section_id == sid
    ).all()

    result = []
    for ss in student_sections:
        u = db.query(User).filter(User.user_id == ss.student_id).first()
        if u:
            result.append({
                "student_id": u.user_id,
                "name": u.name,
                "email": u.email,
                "department": u.department,
                "enrolled_at": str(ss.enrolled_at),
            })
    return {"students": result, "section_id": sid}


# ── Student progress report ───────────────────────────────────────────────────

@router.get("/students/{student_id}/report")
def get_student_report(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """Get a student's full progress report: marks and attendance across all courses."""
    # Verify student belongs to DC's section
    if current_user.role == "degree_coordinator":
        section = _get_dc_section(current_user, db)
        in_section = db.query(StudentSection).filter(
            StudentSection.student_id == student_id,
            StudentSection.section_id == section.section_id,
        ).first()
        if not in_section:
            raise HTTPException(status_code=403, detail="Student not in your section.")

    student = db.query(User).filter(
        User.user_id == student_id, User.role == "student"
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == student_id
    ).all()

    courses_report = []
    for enr in enrollments:
        course = db.query(Course).filter(Course.course_id == enr.course_id).first()
        if not course:
            continue
        teacher = db.query(User).filter(User.user_id == course.teacher_id).first()
        marks = db.query(MarkRecord).filter(
            MarkRecord.course_id == enr.course_id,
            MarkRecord.student_id == student_id,
        ).order_by(MarkRecord.category, MarkRecord.title).all()

        by_cat: dict[str, list] = {
            "attendance": [], "quiz": [], "activity": [], "mid": [], "final": []
        }
        for m in marks:
            if m.category in by_cat:
                by_cat[m.category].append({
                    "record_id": m.record_id,
                    "title": m.title,
                    "marks_obtained": float(m.marks_obtained) if m.marks_obtained is not None else None,
                    "total_marks": float(m.total_marks) if m.total_marks is not None else None,
                })

        # Category lock status
        locks = {
            lock.category: lock.is_locked
            for lock in db.query(CategoryLock).filter(
                CategoryLock.course_id == enr.course_id
            ).all()
        }

        courses_report.append({
            "course_id": course.course_id,
            "code": course.code,
            "name": course.name,
            "section": course.section,
            "teacher_name": teacher.name if teacher else "?",
            "marks": by_cat,
            "locks": locks,
        })

    return {
        "student_id": student.user_id,
        "name": student.name,
        "email": student.email,
        "courses": courses_report,
    }


# ── Teachers teaching this section ────────────────────────────────────────────

@router.get("/teachers")
def get_section_teachers(
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """List teachers who have courses assigned to the DC's section (program/department)."""
    if current_user.role == "degree_coordinator":
        section = _get_dc_section(current_user, db)
        sec_name = section.name
        program = section.program
    else:
        if not section_id:
            raise HTTPException(status_code=400, detail="section_id required.")
        sec = db.query(Section).filter(Section.section_id == section_id).first()
        sec_name = sec.name if sec else None
        program = sec.program if sec else None

    # Teachers by department match (program == department)
    dept_teachers: dict[int, dict] = {}
    if program:
        dept_q = db.query(User).filter(
            User.role == "teacher",
            User.is_active.is_(True),
            User.department == program,
        ).all()
        for t in dept_q:
            dept_teachers[t.user_id] = {
                "teacher_id": t.user_id,
                "name": t.name,
                "email": t.email,
                "department": t.department,
                "courses": [],
            }

    # Also include teachers with courses for this section name
    courses = db.query(Course).filter(
        Course.section == sec_name,
        Course.is_active.is_(True),
    ).all() if sec_name else []

    teachers_map: dict[int, dict] = dict(dept_teachers)
    for c in courses:
        if c.teacher_id and c.teacher_id not in teachers_map:
            teacher = db.query(User).filter(User.user_id == c.teacher_id).first()
            if teacher:
                teachers_map[c.teacher_id] = {
                    "teacher_id": teacher.user_id,
                    "name": teacher.name,
                    "email": teacher.email,
                    "department": teacher.department,
                    "courses": [],
                }
        if c.teacher_id and c.teacher_id in teachers_map:
            teachers_map[c.teacher_id]["courses"].append({
                "course_id": c.course_id,
                "code": c.code,
                "name": c.name,
            })

    return {"teachers": list(teachers_map.values())}


# ── Students taught by a specific teacher ─────────────────────────────────────

@router.get("/teachers/{teacher_id}/students")
def get_teacher_students(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """List all students enrolled in courses taught by a given teacher.

    The DC can query this for any teacher associated with their section.
    Students from outside the DC's own department are included.
    """
    # Verify teacher is associated with DC's section (for DC role)
    if current_user.role == "degree_coordinator":
        section = _get_dc_section(current_user, db)
        # Teacher must have at least one course in this section name
        has_course_in_section = db.query(Course).filter(
            Course.teacher_id == teacher_id,
            Course.section == section.name,
            Course.is_active.is_(True),
        ).first()
        # Also allow teachers from the same department
        teacher_obj = db.query(User).filter(User.user_id == teacher_id).first()
        same_dept = teacher_obj and teacher_obj.department == section.program
        if not has_course_in_section and not same_dept:
            raise HTTPException(
                status_code=403,
                detail="This teacher is not associated with your section.",
            )

    # Find all active courses for this teacher
    courses = db.query(Course).filter(
        Course.teacher_id == teacher_id,
        Course.is_active.is_(True),
    ).all()

    teacher = db.query(User).filter(User.user_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    courses_with_students = []
    for c in courses:
        enrollments = db.query(Enrollment).filter(Enrollment.course_id == c.course_id).all()
        students = []
        for enr in enrollments:
            s = db.query(User).filter(User.user_id == enr.student_id).first()
            if s:
                students.append({
                    "student_id": s.user_id,
                    "name": s.name,
                    "email": s.email,
                    "department": s.department,
                })
        courses_with_students.append({
            "course_id": c.course_id,
            "code": c.code,
            "name": c.name,
            "section": c.section,
            "semester": c.semester,
            "students": students,
        })

    return {
        "teacher_id": teacher_id,
        "teacher_name": teacher.name,
        "teacher_department": teacher.department,
        "courses": courses_with_students,
    }



# ── Schedule for this section ─────────────────────────────────────────────────

@router.get("/schedule")
def get_section_schedule(
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """Get the class schedule for the coordinator's section."""
    if current_user.role == "degree_coordinator":
        section = _get_dc_section(current_user, db)
        sec_name = section.name
    else:
        if not section_id:
            raise HTTPException(status_code=400, detail="section_id required.")
        sec = db.query(Section).filter(Section.section_id == section_id).first()
        sec_name = sec.name if sec else None

    schedules = db.query(Schedule).filter(
        Schedule.section == sec_name
    ).order_by(Schedule.day_of_week, Schedule.start_time).all() if sec_name else []

    DAY_NAMES = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

    from app.models import Location
    loc_map = {loc.location_id: loc.name for loc in db.query(Location).all()}

    return {
        "schedule": [
            {
                "schedule_id": s.schedule_id,
                "location_name": loc_map.get(s.location_id, "?"),
                "course_code": s.course_code,
                "day": DAY_NAMES.get(s.day_of_week, "?"),
                "start_time": str(s.start_time) if s.start_time else None,
                "end_time": str(s.end_time) if s.end_time else None,
                "notes": s.notes,
            }
            for s in schedules
        ]
    }


# ── Enrollment Request Management ─────────────────────────────────────────────

@router.get("/enrollment-requests")
def list_enrollment_requests(
    section_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """List pending enrollment requests for the coordinator's section."""
    if current_user.role == "degree_coordinator":
        section = _get_dc_section(current_user, db)
        sec_name = section.name
    else:
        if not section_id:
            # Admin sees all
            reqs = db.query(EnrollmentRequest).order_by(
                EnrollmentRequest.created_at.desc()
            ).all()
            return {"requests": _format_enroll_reqs(reqs, db)}
        sec = db.query(Section).filter(Section.section_id == section_id).first()
        sec_name = sec.name if sec else None

    # Get courses with this section name
    course_ids = [
        c.course_id for c in db.query(Course).filter(
            Course.section == sec_name, Course.is_active.is_(True)
        ).all()
    ] if sec_name else []

    reqs = db.query(EnrollmentRequest).filter(
        EnrollmentRequest.course_id.in_(course_ids),
        EnrollmentRequest.status == "pending",
    ).order_by(EnrollmentRequest.created_at.desc()).all()

    return {"requests": _format_enroll_reqs(reqs, db)}


def _format_enroll_reqs(reqs, db):
    result = []
    for r in reqs:
        student = db.query(User).filter(User.user_id == r.student_id).first()
        course = db.query(Course).filter(Course.course_id == r.course_id).first()
        teacher = db.query(User).filter(User.user_id == course.teacher_id).first() if course else None
        result.append({
            "request_id": r.request_id,
            "student_id": r.student_id,
            "student_name": student.name if student else "?",
            "student_email": student.email if student else "?",
            "course_id": r.course_id,
            "course_code": course.code if course else "?",
            "course_name": course.name if course else "?",
            "teacher_name": teacher.name if teacher else "?",
            "status": r.status,
            "created_at": str(r.created_at),
        })
    return result


@router.post("/enrollment-requests/{request_id}/approve")
def approve_enrollment(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """DC or admin approves an enrollment request."""
    req = db.query(EnrollmentRequest).filter(
        EnrollmentRequest.request_id == request_id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}.")

    # Check if already enrolled
    existing = db.query(Enrollment).filter(
        Enrollment.student_id == req.student_id,
        Enrollment.course_id == req.course_id,
    ).first()
    if not existing:
        enr = Enrollment(student_id=req.student_id, course_id=req.course_id)
        db.add(enr)

    req.status = "approved"
    req.reviewed_by = current_user.user_id
    req.reviewed_at = datetime.utcnow()
    db.commit()
    return {"message": "Enrollment approved.", "request_id": request_id}


@router.post("/enrollment-requests/{request_id}/reject")
def reject_enrollment(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """DC or admin rejects an enrollment request."""
    req = db.query(EnrollmentRequest).filter(
        EnrollmentRequest.request_id == request_id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}.")

    req.status = "rejected"
    req.reviewed_by = current_user.user_id
    req.reviewed_at = datetime.utcnow()
    db.commit()
    return {"message": "Enrollment rejected.", "request_id": request_id}


class BulkActionRequest(BaseModel):
    request_ids: List[int]


@router.post("/enrollment-requests/bulk-approve")
def bulk_approve_enrollment(
    payload: BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """Bulk approve multiple enrollment requests."""
    approved = []
    for rid in payload.request_ids:
        req = db.query(EnrollmentRequest).filter(
            EnrollmentRequest.request_id == rid,
            EnrollmentRequest.status == "pending",
        ).first()
        if not req:
            continue
        existing = db.query(Enrollment).filter(
            Enrollment.student_id == req.student_id,
            Enrollment.course_id == req.course_id,
        ).first()
        if not existing:
            db.add(Enrollment(student_id=req.student_id, course_id=req.course_id))
        req.status = "approved"
        req.reviewed_by = current_user.user_id
        req.reviewed_at = datetime.utcnow()
        approved.append(rid)
    db.commit()
    return {"message": f"Approved {len(approved)} requests.", "approved": approved}


@router.post("/enrollment-requests/bulk-reject")
def bulk_reject_enrollment(
    payload: BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: User = _dc_or_admin,
):
    """Bulk reject multiple enrollment requests."""
    rejected = []
    for rid in payload.request_ids:
        req = db.query(EnrollmentRequest).filter(
            EnrollmentRequest.request_id == rid,
            EnrollmentRequest.status == "pending",
        ).first()
        if not req:
            continue
        req.status = "rejected"
        req.reviewed_by = current_user.user_id
        req.reviewed_at = datetime.utcnow()
        rejected.append(rid)
    db.commit()
    return {"message": f"Rejected {len(rejected)} requests.", "rejected": rejected}
