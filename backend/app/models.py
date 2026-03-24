from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Text,
    DECIMAL,
    Time,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


# ── Existing models ────────────────────────────────────────────────────────

class Location(Base):
    """Represents a physical campus location (room, lab, office, etc.)."""

    __tablename__ = "locations"

    location_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    category = Column(String(50))  # 'Lab', 'Classroom', 'Office', 'Cafe'
    wing_name = Column(String(50))  # 'Old Campus', 'New Campus'
    floor_level = Column(Integer)
    latitude = Column(DECIMAL(10, 8))
    longitude = Column(DECIMAL(11, 8))
    is_active = Column(Boolean, default=True)

    schedules = relationship("Schedule", back_populates="location")
    lost_found_items = relationship("ItemLostFound", back_populates="last_seen_location")


class Schedule(Base):
    """Timetable entry linking a course to a location and time slot."""

    __tablename__ = "schedules"

    schedule_id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(Integer, ForeignKey("locations.location_id"))
    course_code = Column(String(20))
    day_of_week = Column(Integer)  # 1 (Mon) to 7 (Sun)
    start_time = Column(Time)
    end_time = Column(Time)
    section = Column(String(20))
    notes = Column(Text)

    location = relationship("Location", back_populates="schedules")


class ItemLostFound(Base):
    """Community lost-and-found board entry."""

    __tablename__ = "items_lost_found"

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    item_name = Column(String(100))
    description = Column(Text)
    image_url = Column(String(255))
    # 'Lost', 'Found', 'Claimed', 'Closed'
    status = Column(String(20))
    location_last_seen = Column(Integer, ForeignKey("locations.location_id"))
    created_at = Column(TIMESTAMP, server_default=func.now())
    closed_by = Column(Integer)  # user_id of SAC/admin who closed it

    last_seen_location = relationship("Location", back_populates="lost_found_items")


class Faculty(Base):
    """Faculty members with office location information."""

    __tablename__ = "faculty"

    faculty_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    designation = Column(String(100))
    department = Column(String(100))
    office_location_id = Column(Integer, ForeignKey("locations.location_id"))
    is_available = Column(Boolean, default=True)

    office_location = relationship("Location")


# ── New Auth / Role models ─────────────────────────────────────────────────

class User(Base):
    """Portal user with role-based access."""

    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Roles: admin | teacher | student | sac | head_clerk
    role = Column(String(30), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    courses_taught = relationship("Course", back_populates="teacher",
                                  foreign_keys="Course.teacher_id")
    enrollments = relationship("Enrollment", back_populates="student",
                               foreign_keys="Enrollment.student_id")


class SignupRequest(Base):
    """Pending signup requests waiting for admin approval."""

    __tablename__ = "signup_requests"

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Roles: teacher | student | sac | head_clerk  (admin never self-registers)
    role_requested = Column(String(30), nullable=False)
    # pending | approved | rejected
    status = Column(String(20), default="pending")
    created_at = Column(TIMESTAMP, server_default=func.now())


# ── Academic models ────────────────────────────────────────────────────────

class Course(Base):
    """An academic course taught by a teacher."""

    __tablename__ = "courses"

    course_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.user_id"))
    section = Column(String(20))
    semester = Column(String(30))
    is_active = Column(Boolean, default=True)

    teacher = relationship("User", back_populates="courses_taught",
                           foreign_keys=[teacher_id])
    enrollments = relationship("Enrollment", back_populates="course")
    mark_records = relationship("MarkRecord", back_populates="course")
    category_locks = relationship("CategoryLock", back_populates="course")


class Enrollment(Base):
    """Maps a student to a course they are enrolled in."""

    __tablename__ = "enrollments"

    enrollment_id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "course_id"),)

    student = relationship("User", back_populates="enrollments",
                           foreign_keys=[student_id])
    course = relationship("Course", back_populates="enrollments")


class MarkRecord(Base):
    """One mark entry for a student in a course (quiz, mid, final, etc.)."""

    __tablename__ = "mark_records"

    record_id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    # attendance | quiz | activity | mid | final
    category = Column(String(30), nullable=False)
    title = Column(String(100), nullable=False)  # e.g. "Quiz 1", "Mid Exam"
    marks_obtained = Column(DECIMAL(6, 2))
    total_marks = Column(DECIMAL(6, 2))
    uploaded_by = Column(Integer, ForeignKey("users.user_id"))
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    student = relationship("User", foreign_keys=[student_id])
    course = relationship("Course", back_populates="mark_records")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class CategoryLock(Base):
    """Tracks final-submission lock per course + category.

    Once locked, only an admin can unlock it.
    """

    __tablename__ = "category_locks"

    lock_id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    # attendance | quiz | activity | mid | final
    category = Column(String(30), nullable=False)
    is_locked = Column(Boolean, default=True)
    locked_by = Column(Integer, ForeignKey("users.user_id"))
    locked_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (UniqueConstraint("course_id", "category"),)

    course = relationship("Course", back_populates="category_locks")
    locker = relationship("User", foreign_keys=[locked_by])


class MarkChangeRequest(Base):
    """Request raised by a teacher to amend a mark in a finalized category.

    Admin must accept the request before marks are updated.
    """

    __tablename__ = "mark_change_requests"

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    teacher_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    record_id = Column(Integer, ForeignKey("mark_records.record_id"), nullable=False)
    category = Column(String(30), nullable=False)
    new_marks_obtained = Column(DECIMAL(6, 2), nullable=False)
    new_total_marks = Column(DECIMAL(6, 2))
    reason = Column(Text, nullable=False)
    # pending | accepted | rejected
    status = Column(String(20), default="pending")
    created_at = Column(TIMESTAMP, server_default=func.now())
    reviewed_by = Column(Integer, ForeignKey("users.user_id"))
    reviewed_at = Column(TIMESTAMP)

    teacher = relationship("User", foreign_keys=[teacher_id])
    student = relationship("User", foreign_keys=[student_id])
    course = relationship("Course")
    record = relationship("MarkRecord")
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class CourseRequest(Base):
    """Request by head_clerk to register a new course (needs admin approval)."""

    __tablename__ = "course_requests"

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    clerk_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    code = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    section = Column(String(20))
    semester = Column(String(30))
    # pending | approved | rejected
    status = Column(String(20), default="pending")
    created_at = Column(TIMESTAMP, server_default=func.now())
    reviewed_by = Column(Integer, ForeignKey("users.user_id"))
    reviewed_at = Column(TIMESTAMP)

    clerk = relationship("User", foreign_keys=[clerk_id])
    teacher = relationship("User", foreign_keys=[teacher_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class EnrollmentRequest(Base):
    """Request by a student to enroll in a course (needs admin approval)."""

    __tablename__ = "enrollment_requests"

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    # pending | approved | rejected
    status = Column(String(20), default="pending")
    created_at = Column(TIMESTAMP, server_default=func.now())
    reviewed_by = Column(Integer, ForeignKey("users.user_id"))
    reviewed_at = Column(TIMESTAMP)

    student = relationship("User", foreign_keys=[student_id])
    course = relationship("Course")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
