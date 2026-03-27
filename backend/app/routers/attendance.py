"""Attendance router — daily attendance tracking with fine and exam-eligibility enforcement.

Business rules
--------------
* Teachers (or admin) mark attendance per course per date as present | absent | late.
* Late counts as present for the purpose of percentage calculation.
* Attendance % = (present + late) / total_classes_held × 100.
* Below 75 % → an online fine of PKR 500 is automatically issued.
* Below 70 % → the student is flagged as exam-ineligible.
* Re-marking attendance recalculates the fine status in real time.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth_utils import get_current_user, require_role
from app.database import get_db
from app.models import AttendanceFine, Course, DailyAttendance, Enrollment, User

router = APIRouter(prefix="/api/v1/attendance", tags=["Attendance"])

# ── Thresholds & defaults ─────────────────────────────────────────────────────

FINE_THRESHOLD: float = 75.0        # attendance % below which a fine is issued
EXAM_BLOCK_THRESHOLD: float = 70.0  # attendance % below which exams are blocked
DEFAULT_FINE_AMOUNT: float = 500.00  # fine amount in PKR


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AttendanceEntry(BaseModel):
    student_id: int
    status: str = Field(..., description="present | absent | late")


class MarkAttendanceRequest(BaseModel):
    course_id: int
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    entries: List[AttendanceEntry]


class FinePayRequest(BaseModel):
    pass  # no body needed – presence of the call is the signal


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_course_or_404(db: Session, course_id: int) -> Course:
    """Return the course or raise HTTP 404."""
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    return course


def _attendance_summary(db: Session, student_id: int, course_id: int) -> dict:
    """Return attendance counts and derived flags for one student in one course."""
    records = db.query(DailyAttendance).filter(
        DailyAttendance.student_id == student_id,
        DailyAttendance.course_id == course_id,
    ).all()

    total = len(records)
    if total == 0:
        return {
            "total_classes": 0,
            "present": 0,
            "absent": 0,
            "late": 0,
            "percentage": 0.0,
            "fine_required": False,
            "exam_eligible": True,
        }

    present = sum(1 for r in records if r.status == "present")
    late = sum(1 for r in records if r.status == "late")
    absent = sum(1 for r in records if r.status == "absent")
    effective_present = present + late          # late counts toward attendance
    percentage = round(effective_present / total * 100.0, 2)

    return {
        "total_classes": total,
        "present": present,
        "absent": absent,
        "late": late,
        "percentage": percentage,
        "fine_required": percentage < FINE_THRESHOLD,
        "exam_eligible": percentage >= EXAM_BLOCK_THRESHOLD,
    }


def _evaluate_fines(db: Session, student_id: int, course_id: int, issued_by: int) -> None:
    """Issue, update, or remove an attendance fine after each attendance change."""
    summary = _attendance_summary(db, student_id, course_id)

    if summary["total_classes"] == 0:
        return

    percentage = summary["percentage"]
    existing = db.query(AttendanceFine).filter(
        AttendanceFine.student_id == student_id,
        AttendanceFine.course_id == course_id,
    ).first()

    if percentage < FINE_THRESHOLD:
        reason = (
            f"Attendance {percentage:.1f}% is below the required {FINE_THRESHOLD:.0f}% threshold "
            f"({summary['present'] + summary['late']}/{summary['total_classes']} classes attended)."
        )
        if existing:
            existing.attendance_percentage = percentage
            existing.reason = reason
            existing.issued_by = issued_by
            if existing.status != "waived":
                existing.status = "pending"
        else:
            db.add(AttendanceFine(
                student_id=student_id,
                course_id=course_id,
                attendance_percentage=percentage,
                fine_amount=DEFAULT_FINE_AMOUNT,
                reason=reason,
                status="pending",
                issued_by=issued_by,
            ))
    else:
        # Attendance is now above threshold — remove any pending fine
        if existing and existing.status == "pending":
            db.delete(existing)

    db.commit()


def _fine_dict(fine: AttendanceFine) -> dict:
    return {
        "fine_id": fine.fine_id,
        "amount": float(fine.fine_amount),
        "attendance_percentage": float(fine.attendance_percentage) if fine.attendance_percentage is not None else None,
        "status": fine.status,
        "issued_at": str(fine.issued_at),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/mark", status_code=201)
def mark_attendance_batch(
    payload: MarkAttendanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Mark daily attendance for one or more students in a course.

    Re-submitting the same (course_id, date, student_id) will overwrite the
    previous status (upsert), allowing corrections before the category is
    finalized.  Fines are recalculated immediately for each affected student.
    """
    course = _get_course_or_404(db, payload.course_id)
    if current_user.role == "teacher" and course.teacher_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your course.")

    valid_statuses = {"present", "absent", "late"}
    results = []

    for entry in payload.entries:
        if entry.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{entry.status}'. Allowed: present | absent | late",
            )

        # Student must be enrolled
        enrolled = db.query(Enrollment).filter(
            Enrollment.course_id == payload.course_id,
            Enrollment.student_id == entry.student_id,
        ).first()
        if not enrolled:
            results.append({
                "student_id": entry.student_id,
                "result": "skipped",
                "detail": "Student not enrolled in this course.",
            })
            continue

        existing = db.query(DailyAttendance).filter(
            DailyAttendance.student_id == entry.student_id,
            DailyAttendance.course_id == payload.course_id,
            DailyAttendance.date == payload.date,
        ).first()

        if existing:
            existing.status = entry.status
            existing.marked_by = current_user.user_id
        else:
            db.add(DailyAttendance(
                student_id=entry.student_id,
                course_id=payload.course_id,
                date=payload.date,
                status=entry.status,
                marked_by=current_user.user_id,
            ))

        results.append({"student_id": entry.student_id, "result": "ok"})

    db.commit()

    # Recalculate fines for every successfully processed student
    for entry in payload.entries:
        enrolled = db.query(Enrollment).filter(
            Enrollment.course_id == payload.course_id,
            Enrollment.student_id == entry.student_id,
        ).first()
        if enrolled:
            _evaluate_fines(db, entry.student_id, payload.course_id, current_user.user_id)

    return {"message": "Attendance marked.", "date": payload.date, "results": results}


@router.get("/{course_id}/records")
def get_attendance_records(
    course_id: int,
    date: Optional[str] = None,
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return raw daily attendance records for a course.

    * Teachers / admin can filter by optional ``date`` and ``student_id``.
    * Students see only their own records.
    """
    course = _get_course_or_404(db, course_id)

    if current_user.role == "student":
        enrolled = db.query(Enrollment).filter(
            Enrollment.course_id == course_id,
            Enrollment.student_id == current_user.user_id,
        ).first()
        if not enrolled:
            raise HTTPException(status_code=403, detail="Not enrolled in this course.")
        query = db.query(DailyAttendance).filter(
            DailyAttendance.course_id == course_id,
            DailyAttendance.student_id == current_user.user_id,
        )
    elif current_user.role == "teacher":
        if course.teacher_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Not your course.")
        query = db.query(DailyAttendance).filter(DailyAttendance.course_id == course_id)
        if student_id:
            query = query.filter(DailyAttendance.student_id == student_id)
    else:
        # admin and other elevated roles
        query = db.query(DailyAttendance).filter(DailyAttendance.course_id == course_id)
        if student_id:
            query = query.filter(DailyAttendance.student_id == student_id)

    if date:
        query = query.filter(DailyAttendance.date == date)

    records = query.order_by(DailyAttendance.date.desc()).all()
    return {
        "course_id": course_id,
        "records": [
            {
                "record_id": r.record_id,
                "student_id": r.student_id,
                "date": r.date,
                "status": r.status,
                "marked_by": r.marked_by,
                "created_at": str(r.created_at),
            }
            for r in records
        ],
    }


@router.get("/{course_id}/summary")
def get_attendance_summary(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return attendance % and enrollment-status flags for each student.

    * ``fine_required``  → attendance < 75 % (a PKR 500 fine is issued online).
    * ``exam_eligible``  → False when attendance < 70 % (barred from exams).
    """
    course = _get_course_or_404(db, course_id)

    if current_user.role == "student":
        enrolled = db.query(Enrollment).filter(
            Enrollment.course_id == course_id,
            Enrollment.student_id == current_user.user_id,
        ).first()
        if not enrolled:
            raise HTTPException(status_code=403, detail="Not enrolled in this course.")
        student = db.query(User).filter(User.user_id == current_user.user_id).first()
        summary = _attendance_summary(db, current_user.user_id, course_id)
        fine = db.query(AttendanceFine).filter(
            AttendanceFine.student_id == current_user.user_id,
            AttendanceFine.course_id == course_id,
        ).first()
        students_list = [{
            "student_id": current_user.user_id,
            "name": student.name if student else "?",
            "email": student.email if student else "?",
            **summary,
            "fine": _fine_dict(fine) if fine else None,
        }]
    else:
        if current_user.role == "teacher" and course.teacher_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Not your course.")

        enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
        students_list = []
        for enr in enrollments:
            student = db.query(User).filter(User.user_id == enr.student_id).first()
            if not student:
                continue
            summary = _attendance_summary(db, enr.student_id, course_id)
            fine = db.query(AttendanceFine).filter(
                AttendanceFine.student_id == enr.student_id,
                AttendanceFine.course_id == course_id,
            ).first()
            students_list.append({
                "student_id": enr.student_id,
                "name": student.name,
                "email": student.email,
                **summary,
                "fine": _fine_dict(fine) if fine else None,
            })

    return {
        "course_id": course_id,
        "students": students_list,
        "fine_threshold": FINE_THRESHOLD,
        "exam_block_threshold": EXAM_BLOCK_THRESHOLD,
    }


@router.post("/{course_id}/evaluate", status_code=200)
def evaluate_course_attendance(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "admin")),
):
    """Manually trigger fine evaluation for all students in a course.

    Useful at the end of a marking session to ensure all fines are up to date.
    Returns a summary of each student's attendance status.
    """
    course = _get_course_or_404(db, course_id)
    if current_user.role == "teacher" and course.teacher_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your course.")

    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    evaluated = []

    for enr in enrollments:
        _evaluate_fines(db, enr.student_id, course_id, current_user.user_id)
        summary = _attendance_summary(db, enr.student_id, course_id)
        student = db.query(User).filter(User.user_id == enr.student_id).first()
        evaluated.append({
            "student_id": enr.student_id,
            "name": student.name if student else "?",
            "percentage": summary["percentage"],
            "fine_issued": summary["fine_required"],
            "exam_eligible": summary["exam_eligible"],
        })

    return {
        "course_id": course_id,
        "evaluated": evaluated,
        "fine_threshold": FINE_THRESHOLD,
        "exam_block_threshold": EXAM_BLOCK_THRESHOLD,
    }


@router.get("/exam-eligibility/{course_id}")
def get_exam_eligibility(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return exam eligibility per student based on attendance.

    Students with attendance < 70 % are **not eligible** to sit in exams.
    Students see only their own result; teachers/admin see the full list.
    """
    course = _get_course_or_404(db, course_id)

    if current_user.role == "student":
        enrolled = db.query(Enrollment).filter(
            Enrollment.course_id == course_id,
            Enrollment.student_id == current_user.user_id,
        ).first()
        if not enrolled:
            raise HTTPException(status_code=403, detail="Not enrolled in this course.")
        summary = _attendance_summary(db, current_user.user_id, course_id)
        return {
            "course_id": course_id,
            "student_id": current_user.user_id,
            "attendance_percentage": summary["percentage"],
            "exam_eligible": summary["exam_eligible"],
            "fine_required": summary["fine_required"],
            "exam_block_threshold": EXAM_BLOCK_THRESHOLD,
            "fine_threshold": FINE_THRESHOLD,
        }

    if current_user.role == "teacher" and course.teacher_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your course.")

    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    result = []
    for enr in enrollments:
        student = db.query(User).filter(User.user_id == enr.student_id).first()
        summary = _attendance_summary(db, enr.student_id, course_id)
        result.append({
            "student_id": enr.student_id,
            "name": student.name if student else "?",
            "email": student.email if student else "?",
            "attendance_percentage": summary["percentage"],
            "exam_eligible": summary["exam_eligible"],
            "fine_required": summary["fine_required"],
        })

    return {
        "course_id": course_id,
        "students": result,
        "exam_block_threshold": EXAM_BLOCK_THRESHOLD,
        "fine_threshold": FINE_THRESHOLD,
    }


@router.get("/fines")
def list_fines(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List attendance fines.

    * Students see only their own fines.
    * Teachers see fines for students in their courses.
    * Admin sees all fines.
    """
    if current_user.role == "student":
        query = db.query(AttendanceFine).filter(
            AttendanceFine.student_id == current_user.user_id
        )
    elif current_user.role == "teacher":
        # Only fines for courses this teacher teaches
        teacher_course_ids = [
            c.course_id
            for c in db.query(Course).filter(Course.teacher_id == current_user.user_id).all()
        ]
        query = db.query(AttendanceFine).filter(
            AttendanceFine.course_id.in_(teacher_course_ids)
        )
        if course_id:
            if course_id not in teacher_course_ids:
                raise HTTPException(status_code=403, detail="Not your course.")
            query = query.filter(AttendanceFine.course_id == course_id)
    elif current_user.role in ("admin", "degree_coordinator", "head_clerk"):
        query = db.query(AttendanceFine)
        if course_id:
            query = query.filter(AttendanceFine.course_id == course_id)
    else:
        raise HTTPException(status_code=403, detail="Access denied.")

    fines = query.order_by(AttendanceFine.issued_at.desc()).all()
    result = []
    for f in fines:
        student = db.query(User).filter(User.user_id == f.student_id).first()
        course = db.query(Course).filter(Course.course_id == f.course_id).first()
        result.append({
            "fine_id": f.fine_id,
            "student_id": f.student_id,
            "student_name": student.name if student else "?",
            "student_email": student.email if student else "?",
            "course_id": f.course_id,
            "course_code": course.code if course else "?",
            "course_name": course.name if course else "?",
            "attendance_percentage": float(f.attendance_percentage) if f.attendance_percentage is not None else None,
            "fine_amount": float(f.fine_amount),
            "reason": f.reason,
            "status": f.status,
            "issued_at": str(f.issued_at),
        })

    return {
        "fines": result,
        "fine_threshold": FINE_THRESHOLD,
        "exam_block_threshold": EXAM_BLOCK_THRESHOLD,
    }


@router.put("/fines/{fine_id}/pay")
def mark_fine_paid(
    fine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Mark a fine as paid (admin only)."""
    fine = db.query(AttendanceFine).filter(AttendanceFine.fine_id == fine_id).first()
    if not fine:
        raise HTTPException(status_code=404, detail="Fine not found.")
    if fine.status == "paid":
        raise HTTPException(status_code=400, detail="Fine is already marked as paid.")
    fine.status = "paid"
    db.commit()
    return {"message": "Fine marked as paid.", "fine_id": fine_id}


@router.put("/fines/{fine_id}/waive")
def waive_fine(
    fine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Waive a fine (admin only)."""
    fine = db.query(AttendanceFine).filter(AttendanceFine.fine_id == fine_id).first()
    if not fine:
        raise HTTPException(status_code=404, detail="Fine not found.")
    fine.status = "waived"
    db.commit()
    return {"message": "Fine waived.", "fine_id": fine_id}
