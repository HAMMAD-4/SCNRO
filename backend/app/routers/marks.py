"""Marks router — academic marks management for teachers and students."""

from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth_utils import get_current_user, require_role
from app.database import get_db
from app.models import CategoryLock, Course, Enrollment, MarkRecord, User

router = APIRouter(prefix="/api/v1", tags=["Marks"])

VALID_CATEGORIES = {"attendance", "quiz", "activity", "mid", "final"}


# ── Schemas ─────────────────────────────────────────────────────────────────

class CourseCreate(BaseModel):
    code: str
    name: str
    section: Optional[str] = None
    semester: Optional[str] = None


class MarkRecordCreate(BaseModel):
    student_id: int
    course_id: int
    category: str = Field(..., description="attendance | quiz | activity | mid | final")
    title: str = Field(..., max_length=100)
    marks_obtained: Optional[float] = None
    total_marks: Optional[float] = None


class MarkRecordUpdate(BaseModel):
    title: Optional[str] = None
    marks_obtained: Optional[float] = None
    total_marks: Optional[float] = None


# ── Course endpoints ─────────────────────────────────────────────────────────

@router.get("/courses/available")
def list_available_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active courses available for enrollment (any student, any department)."""
    courses = db.query(Course).filter(Course.is_active.is_(True)).all()
    result = []
    for c in courses:
        teacher = db.query(User).filter(User.user_id == c.teacher_id).first()
        # Check if student is already enrolled
        already_enrolled = False
        if current_user.role == "student":
            already_enrolled = db.query(Enrollment).filter(
                Enrollment.student_id == current_user.user_id,
                Enrollment.course_id == c.course_id,
            ).first() is not None
        result.append({
            "course_id": c.course_id,
            "code": c.code,
            "name": c.name,
            "section": c.section,
            "semester": c.semester,
            "teacher_name": teacher.name if teacher else None,
            "teacher_department": teacher.department if teacher else None,
            "already_enrolled": already_enrolled,
        })
    return {"courses": result}


@router.get("/courses")
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Teachers see their own courses; students see enrolled courses; admin sees all."""
    if current_user.role == "teacher":
        courses = db.query(Course).filter(
            Course.teacher_id == current_user.user_id,
            Course.is_active.is_(True),
        ).all()
    elif current_user.role == "student":
        courses = (
            db.query(Course)
            .join(Enrollment, Enrollment.course_id == Course.course_id)
            .filter(Enrollment.student_id == current_user.user_id, Course.is_active.is_(True))
            .all()
        )
    else:
        # admin, sac, head_clerk see all active courses
        courses = db.query(Course).filter(Course.is_active.is_(True)).all()

    result = []
    for c in courses:
        teacher = db.query(User).filter(User.user_id == c.teacher_id).first()
        result.append({
            "course_id": c.course_id,
            "code": c.code,
            "name": c.name,
            "section": c.section,
            "semester": c.semester,
            "teacher_name": teacher.name if teacher else None,
            "teacher_id": c.teacher_id,
        })
    return {"courses": result}


@router.post("/courses", status_code=201)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Create a new course (admin or the teacher themselves)."""
    course = Course(
        code=payload.code,
        name=payload.name,
        teacher_id=current_user.user_id if current_user.role == "teacher" else None,
        section=payload.section,
        semester=payload.semester,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return {"course_id": course.course_id, "code": course.code, "name": course.name}


@router.get("/courses/{course_id}/students")
def list_enrolled_students(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """List students enrolled in a course (teacher of that course or admin)."""
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    if current_user.role == "teacher" and course.teacher_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your course.")

    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.course_id == course_id)
        .all()
    )
    students = []
    for e in enrollments:
        u = db.query(User).filter(User.user_id == e.student_id).first()
        if u:
            students.append({
                "enrollment_id": e.enrollment_id,
                "student_id": u.user_id,
                "name": u.name,
                "email": u.email,
            })
    return {"students": students}


@router.post("/courses/{course_id}/enroll", status_code=201)
def enroll_student(
    course_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Enroll a student in a course."""
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    if current_user.role == "teacher" and course.teacher_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your course.")

    student = db.query(User).filter(
        User.user_id == student_id, User.role == "student"
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    existing = db.query(Enrollment).filter(
        Enrollment.course_id == course_id,
        Enrollment.student_id == student_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Student already enrolled.")

    enr = Enrollment(student_id=student_id, course_id=course_id)
    db.add(enr)
    db.commit()
    return {"message": "Enrolled.", "student_id": student_id, "course_id": course_id}


@router.delete("/courses/{course_id}/enroll/{student_id}")
def unenroll_student(
    course_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Remove a student from a course."""
    enr = db.query(Enrollment).filter(
        Enrollment.course_id == course_id,
        Enrollment.student_id == student_id,
    ).first()
    if not enr:
        raise HTTPException(status_code=404, detail="Enrollment not found.")
    db.delete(enr)
    db.commit()
    return {"message": "Unenrolled."}


# ── Mark Records ─────────────────────────────────────────────────────────────

def _check_lock(db: Session, course_id: int, category: str):
    """Raise 423 if the category is locked for final submission."""
    lock = db.query(CategoryLock).filter(
        CategoryLock.course_id == course_id,
        CategoryLock.category == category,
        CategoryLock.is_locked == True,  # noqa: E712
    ).first()
    if lock:
        raise HTTPException(
            status_code=423,
            detail=f"Category '{category}' is finalized. Contact admin to unlock.",
        )


@router.get("/courses/{course_id}/marks")
def get_marks(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Teachers get all students' marks; students get only their own."""
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    if current_user.role == "student":
        # Check enrollment
        enr = db.query(Enrollment).filter(
            Enrollment.course_id == course_id,
            Enrollment.student_id == current_user.user_id,
        ).first()
        if not enr:
            raise HTTPException(status_code=403, detail="Not enrolled in this course.")
        records = db.query(MarkRecord).filter(
            MarkRecord.course_id == course_id,
            MarkRecord.student_id == current_user.user_id,
        ).all()
    elif current_user.role == "teacher":
        if course.teacher_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Not your course.")
        records = db.query(MarkRecord).filter(
            MarkRecord.course_id == course_id
        ).all()
    else:
        records = db.query(MarkRecord).filter(
            MarkRecord.course_id == course_id
        ).all()

    # Fetch lock statuses for this course
    locks = {
        lock.category: lock.is_locked
        for lock in db.query(CategoryLock).filter(
            CategoryLock.course_id == course_id
        ).all()
    }

    return {
        "course_id": course_id,
        "marks": [
            {
                "record_id": r.record_id,
                "student_id": r.student_id,
                "category": r.category,
                "title": r.title,
                "marks_obtained": float(r.marks_obtained) if r.marks_obtained is not None else None,
                "total_marks": float(r.total_marks) if r.total_marks is not None else None,
                "uploaded_by": r.uploaded_by,
                "created_at": str(r.created_at),
            }
            for r in records
        ],
        "locks": locks,
    }


@router.get("/courses/{course_id}/locks")
def get_course_locks(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the lock status for all mark categories of a course."""
    locks = {
        lock.category: lock.is_locked
        for lock in db.query(CategoryLock).filter(
            CategoryLock.course_id == course_id
        ).all()
    }
    return {"course_id": course_id, "locks": locks}


@router.get("/marks/my")
def get_my_marks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """Return all mark records for the currently signed-in student across all enrolled courses."""
    records = db.query(MarkRecord).filter(
        MarkRecord.student_id == current_user.user_id
    ).order_by(MarkRecord.course_id, MarkRecord.category, MarkRecord.title).all()
    return {
        "marks": [
            {
                "record_id": r.record_id,
                "course_id": r.course_id,
                "student_id": r.student_id,
                "category": r.category,
                "title": r.title,
                "marks_obtained": float(r.marks_obtained) if r.marks_obtained is not None else None,
                "total_marks": float(r.total_marks) if r.total_marks is not None else None,
            }
            for r in records
        ]
    }


def create_mark(
    payload: MarkRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Upload a mark record for a student."""
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Category must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
        )

    course = db.query(Course).filter(Course.course_id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    if current_user.role == "teacher" and course.teacher_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your course.")

    _check_lock(db, payload.course_id, payload.category)

    # Student must be enrolled
    enr = db.query(Enrollment).filter(
        Enrollment.course_id == payload.course_id,
        Enrollment.student_id == payload.student_id,
    ).first()
    if not enr:
        raise HTTPException(status_code=400, detail="Student is not enrolled in this course.")

    record = MarkRecord(
        student_id=payload.student_id,
        course_id=payload.course_id,
        category=payload.category,
        title=payload.title,
        marks_obtained=payload.marks_obtained,
        total_marks=payload.total_marks,
        uploaded_by=current_user.user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"record_id": record.record_id, "message": "Mark recorded."}


@router.put("/marks/{record_id}")
def update_mark(
    record_id: int,
    payload: MarkRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Update an existing mark record."""
    record = db.query(MarkRecord).filter(MarkRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mark record not found.")

    if current_user.role == "teacher":
        course = db.query(Course).filter(Course.course_id == record.course_id).first()
        if course and course.teacher_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Not your course.")
        _check_lock(db, record.course_id, record.category)

    if payload.title is not None:
        record.title = payload.title
    if payload.marks_obtained is not None:
        record.marks_obtained = payload.marks_obtained
    if payload.total_marks is not None:
        record.total_marks = payload.total_marks

    db.commit()
    return {"message": "Updated.", "record_id": record_id}


@router.delete("/marks/{record_id}")
def delete_mark(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Delete a mark record."""
    record = db.query(MarkRecord).filter(MarkRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mark record not found.")

    if current_user.role == "teacher":
        course = db.query(Course).filter(Course.course_id == record.course_id).first()
        if course and course.teacher_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Not your course.")
        _check_lock(db, record.course_id, record.category)

    db.delete(record)
    db.commit()
    return {"message": "Deleted."}


# ── Final Submission (lock) ──────────────────────────────────────────────────

@router.post("/courses/{course_id}/finalize/{category}")
def finalize_category(
    course_id: int,
    category: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Lock a category for final submission. Only admin can unlock afterwards."""
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    if current_user.role == "teacher" and course.teacher_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your course.")

    lock = db.query(CategoryLock).filter(
        CategoryLock.course_id == course_id,
        CategoryLock.category == category,
    ).first()

    if lock:
        if lock.is_locked:
            raise HTTPException(status_code=400, detail="Already finalized.")
        lock.is_locked = True
        lock.locked_by = current_user.user_id
    else:
        lock = CategoryLock(
            course_id=course_id,
            category=category,
            is_locked=True,
            locked_by=current_user.user_id,
        )
        db.add(lock)

    db.commit()
    return {"message": f"Category '{category}' finalized for course {course_id}."}


# ── Mark Change Requests ─────────────────────────────────────────────────────

class MarkChangeRequestCreate(BaseModel):
    record_id: int
    new_marks_obtained: float
    new_total_marks: Optional[float] = None
    reason: str = Field(..., min_length=5)


@router.post("/marks/change-request", status_code=201)
def create_mark_change_request(
    payload: MarkChangeRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher")),
):
    """Teacher submits a mark amendment request for a finalized category."""
    from app.models import MarkChangeRequest

    record = db.query(MarkRecord).filter(MarkRecord.record_id == payload.record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mark record not found.")

    # Verify teacher owns the course
    course = db.query(Course).filter(Course.course_id == record.course_id).first()
    if not course or course.teacher_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your course.")

    # Category must be finalized
    lock = db.query(CategoryLock).filter(
        CategoryLock.course_id == record.course_id,
        CategoryLock.category == record.category,
        CategoryLock.is_locked.is_(True),
    ).first()
    if not lock:
        raise HTTPException(
            status_code=400,
            detail="Category is not finalized. Edit the mark directly.",
        )

    # Reject if a pending request already exists for this record
    existing = db.query(MarkChangeRequest).filter(
        MarkChangeRequest.record_id == payload.record_id,
        MarkChangeRequest.status == "pending",
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A pending change request already exists for this mark.",
        )

    req = MarkChangeRequest(
        teacher_id=current_user.user_id,
        course_id=record.course_id,
        student_id=record.student_id,
        record_id=payload.record_id,
        category=record.category,
        new_marks_obtained=payload.new_marks_obtained,
        new_total_marks=payload.new_total_marks,
        reason=payload.reason,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {"message": "Change request submitted.", "request_id": req.request_id}


@router.get("/marks/change-requests")
def list_mark_change_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Teachers see their own requests; admin sees all."""
    from app.models import MarkChangeRequest

    q = db.query(MarkChangeRequest)
    if current_user.role == "teacher":
        q = q.filter(MarkChangeRequest.teacher_id == current_user.user_id)
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied.")

    requests = q.order_by(MarkChangeRequest.created_at.desc()).all()
    result = []
    for r in requests:
        student = db.query(User).filter(User.user_id == r.student_id).first()
        teacher = db.query(User).filter(User.user_id == r.teacher_id).first()
        record = db.query(MarkRecord).filter(MarkRecord.record_id == r.record_id).first()
        course = db.query(Course).filter(Course.course_id == r.course_id).first()
        result.append({
            "request_id": r.request_id,
            "teacher_name": teacher.name if teacher else "?",
            "course_code": course.code if course else "?",
            "course_name": course.name if course else "?",
            "student_name": student.name if student else "?",
            "record_title": record.title if record else "?",
            "category": r.category,
            "current_marks": float(record.marks_obtained) if record and record.marks_obtained is not None else None,
            "current_total": float(record.total_marks) if record and record.total_marks is not None else None,
            "new_marks_obtained": float(r.new_marks_obtained) if r.new_marks_obtained is not None else None,
            "new_total_marks": float(r.new_total_marks) if r.new_total_marks is not None else None,
            "reason": r.reason,
            "status": r.status,
            "created_at": str(r.created_at),
        })
    return {"requests": result}


# ── PDF Report ───────────────────────────────────────────────────────────────

@router.get("/courses/{course_id}/report.pdf")
def download_pdf_report(
    course_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Generate and return a PDF result sheet for the course.

    Optionally filter by a single category (e.g. ?category=mid or ?category=final).
    Works even when no marks have been entered yet.
    """
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    if current_user.role == "teacher" and course.teacher_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your course.")

    if category and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    # Collect all enrolled students and their marks
    enrollments = db.query(Enrollment).filter(
        Enrollment.course_id == course_id
    ).all()

    teacher = db.query(User).filter(User.user_id == course.teacher_id).first()

    students_data = []
    for enr in enrollments:
        student = db.query(User).filter(User.user_id == enr.student_id).first()
        if not student:
            continue
        q = db.query(MarkRecord).filter(
            MarkRecord.course_id == course_id,
            MarkRecord.student_id == enr.student_id,
        )
        if category:
            q = q.filter(MarkRecord.category == category)
        marks = q.order_by(MarkRecord.category, MarkRecord.title).all()
        students_data.append((student, marks))

    locks = {
        lock.category: lock.is_locked
        for lock in db.query(CategoryLock).filter(
            CategoryLock.course_id == course_id
        ).all()
    }

    pdf_bytes = _build_pdf(course, teacher, students_data, locks, category)
    cat_suffix = f"_{category}" if category else ""
    filename = f"{course.code}_{course.section or 'ALL'}{cat_suffix}_result.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_pdf(course, teacher, students_data: list, locks: dict, category: Optional[str] = None) -> bytes:
    """Build a PDF result sheet using ReportLab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8, leading=10)
    hdr_style  = ParagraphStyle("hdr",  parent=styles["Normal"], fontSize=9, leading=11,
                                 textColor=colors.white, fontName="Helvetica-Bold")
    title_style = ParagraphStyle("uni_title", parent=styles["Normal"], fontSize=14,
                                  fontName="Helvetica-Bold", alignment=1, leading=18)
    sub_style   = ParagraphStyle("uni_sub",   parent=styles["Normal"], fontSize=10,
                                  alignment=1, leading=13, textColor=colors.HexColor("#444444"))
    elements = []

    # University / campus header
    elements.append(Paragraph("Punjab University College of Information Technology (PUCIT)", title_style))
    elements.append(Paragraph("University of the Punjab, Lahore, Pakistan", sub_style))
    elements.append(Paragraph("Canal Bank Road, Lahore – 54590 | www.pucit.edu.pk", sub_style))
    elements.append(Spacer(1, 0.3*cm))

    # Divider line via a thin table
    divider = Table([[""]], colWidths=[doc.width], rowHeights=[2])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#006633"))]))
    elements.append(divider)
    elements.append(Spacer(1, 0.3*cm))

    # Report title
    report_title = f"Result Gazette — {category.upper() if category else 'All Categories'}"
    elements.append(Paragraph(f"<b>{report_title}</b>", styles["Title"]))

    # Course info
    teacher_name = teacher.name if teacher else "—"
    elements.append(Paragraph(
        f"Course: <b>{course.code}</b> – {course.name} &nbsp;|&nbsp; "
        f"Section: <b>{course.section or '—'}</b> &nbsp;|&nbsp; "
        f"Semester: <b>{course.semester or '—'}</b> &nbsp;|&nbsp; "
        f"Teacher: <b>{teacher_name}</b>",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 0.4*cm))

    # Lock status row
    if category:
        locked = locks.get(category, False)
        lock_status = f"{category}: {'Finalized ✓' if locked else 'Open (not yet finalized)'}"
    else:
        lock_status = " | ".join(
            f"{cat}: {'Final' if locks.get(cat) else 'Open'}"
            for cat in ("attendance", "quiz", "activity", "mid", "final")
        )
    elements.append(Paragraph(f"<i>Status — {lock_status}</i>", styles["Normal"]))
    elements.append(Spacer(1, 0.4*cm))

    if not students_data:
        elements.append(Paragraph("No students enrolled in this course.", styles["Normal"]))
    else:
        # Determine columns: if filtering by category, show just that category
        if category:
            cat_list = [category]
            col_headers = [
                Paragraph(h, hdr_style)
                for h in ["#", "Student", "Email", category.title()]
            ]
            col_widths = [1*cm, 5*cm, 6*cm, 8*cm]
        else:
            cat_list = ["attendance", "quiz", "activity", "mid", "final"]
            col_headers = [
                Paragraph(h, hdr_style)
                for h in ["#", "Student", "Email",
                           "Attendance", "Quiz(s)", "Activity(s)", "Mid", "Final"]
            ]
            col_widths = [1*cm, 4*cm, 5*cm, 3.5*cm, 3.5*cm, 3.5*cm, 3.5*cm, 3.5*cm]

        table_data = [col_headers]

        for idx, (student, marks) in enumerate(students_data, 1):
            by_cat: dict[str, list] = {c: [] for c in VALID_CATEGORIES}
            for m in marks:
                if m.category in by_cat:
                    obt = f"{float(m.marks_obtained):.1f}" if m.marks_obtained is not None else "–"
                    tot = f"/{float(m.total_marks):.1f}" if m.total_marks is not None else ""
                    by_cat[m.category].append(f"{m.title}: {obt}{tot}")

            row_base = [
                Paragraph(str(idx), cell_style),
                Paragraph(student.name, cell_style),
                Paragraph(student.email, cell_style),
            ]
            for cat in cat_list:
                row_base.append(Paragraph("<br/>".join(by_cat[cat]) or "—", cell_style))
            table_data.append(row_base)

        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        alt = colors.HexColor("#EFF3FF")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#006633")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, alt]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(t)

    doc.build(elements)
    return buf.getvalue()


# ── Student Enrollment Requests ──────────────────────────────────────────────

class EnrollmentRequestCreate(BaseModel):
    course_id: int


@router.post("/enrollment-requests", status_code=201)
def create_enrollment_request(
    payload: EnrollmentRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """Student submits an enrollment request for admin approval."""
    from app.models import EnrollmentRequest

    course = db.query(Course).filter(
        Course.course_id == payload.course_id,
        Course.is_active.is_(True),
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    # Already enrolled?
    if db.query(Enrollment).filter(
        Enrollment.student_id == current_user.user_id,
        Enrollment.course_id  == payload.course_id,
    ).first():
        raise HTTPException(status_code=409, detail="Already enrolled in this course.")

    # Pending request already?
    if db.query(EnrollmentRequest).filter(
        EnrollmentRequest.student_id == current_user.user_id,
        EnrollmentRequest.course_id  == payload.course_id,
        EnrollmentRequest.status     == "pending",
    ).first():
        raise HTTPException(status_code=409, detail="Enrollment request already pending.")

    req = EnrollmentRequest(
        student_id=current_user.user_id,
        course_id=payload.course_id,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {"message": "Enrollment request submitted.", "request_id": req.request_id}


@router.get("/enrollment-requests/my")
def list_my_enrollment_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("student")),
):
    """List the current student's enrollment requests."""
    from app.models import EnrollmentRequest

    reqs = db.query(EnrollmentRequest).filter(
        EnrollmentRequest.student_id == current_user.user_id
    ).order_by(EnrollmentRequest.created_at.desc()).all()

    result = []
    for r in reqs:
        course  = db.query(Course).filter(Course.course_id == r.course_id).first()
        teacher = db.query(User).filter(User.user_id == course.teacher_id).first() if course else None
        result.append({
            "request_id":   r.request_id,
            "course_code":  course.code if course else "?",
            "course_name":  course.name if course else "?",
            "teacher_name": teacher.name if teacher else "?",
            "status":       r.status,
            "created_at":   str(r.created_at),
        })
    return {"requests": result}
