import os
from datetime import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base, Course, Enrollment, Faculty, Location, MarkRecord, Schedule, User,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    # Default to SQLite for zero-config local development.
    # Set DATABASE_URL=postgresql://... for staging / production deployments.
    "sqlite:///./scnro_dev.db",
)

_sqlite = DATABASE_URL.startswith("sqlite")

if _sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _seed_locations(db) -> None:
    if db.query(Location).first() is not None:
        return

    locations = [
        Location(location_id=1,  name="Main Entrance",     category="Corridor",  wing_name="Old Campus", floor_level=0, latitude=31.48260, longitude=74.30360),
        Location(location_id=2,  name="CS Block Corridor", category="Corridor",  wing_name="Old Campus", floor_level=1, latitude=31.48270, longitude=74.30370),
        Location(location_id=3,  name="Computer Lab 1",    category="Lab",       wing_name="Old Campus", floor_level=1, latitude=31.48280, longitude=74.30375),
        Location(location_id=4,  name="Computer Lab 2",    category="Lab",       wing_name="Old Campus", floor_level=1, latitude=31.48285, longitude=74.30380),
        Location(location_id=5,  name="Computer Lab 3",    category="Lab",       wing_name="Old Campus", floor_level=2, latitude=31.48290, longitude=74.30385),
        Location(location_id=6,  name="Computer Lab 4",    category="Lab",       wing_name="New Campus", floor_level=1, latitude=31.48295, longitude=74.30390),
        Location(location_id=7,  name="Seminar Hall",      category="Classroom", wing_name="Old Campus", floor_level=1, latitude=31.48265, longitude=74.30365),
        Location(location_id=8,  name="Faculty Block",     category="Corridor",  wing_name="Old Campus", floor_level=2, latitude=31.48300, longitude=74.30395),
        Location(location_id=9,  name="Dean Office",       category="Office",    wing_name="Old Campus", floor_level=2, latitude=31.48310, longitude=74.30400),
        Location(location_id=10, name="Cafeteria",         category="Cafe",      wing_name="Old Campus", floor_level=0, latitude=31.48250, longitude=74.30355),
        Location(location_id=11, name="Lecture Hall A",    category="Classroom", wing_name="New Campus", floor_level=1, latitude=31.48315, longitude=74.30405),
        Location(location_id=12, name="Lecture Hall B",    category="Classroom", wing_name="New Campus", floor_level=2, latitude=31.48320, longitude=74.30410),
        Location(location_id=13, name="Library",           category="Classroom", wing_name="Old Campus", floor_level=1, latitude=31.48245, longitude=74.30350),
        Location(location_id=14, name="Project Room 1",    category="Lab",       wing_name="New Campus", floor_level=2, latitude=31.48325, longitude=74.30415),
        Location(location_id=15, name="Project Room 2",    category="Lab",       wing_name="New Campus", floor_level=2, latitude=31.48330, longitude=74.30420),
    ]
    db.add_all(locations)

    faculty_members = [
        Faculty(name="Dr. Ahmed Khan",    designation="Professor",           department="Computer Science",       office_location_id=9, is_available=True),
        Faculty(name="Dr. Sara Iqbal",    designation="Associate Professor",  department="Software Engineering",   office_location_id=8, is_available=True),
        Faculty(name="Mr. Bilal Hussain", designation="Lecturer",            department="Computer Science",       office_location_id=8, is_available=False),
        Faculty(name="Ms. Fatima Malik",  designation="Lecturer",            department="Information Technology", office_location_id=8, is_available=True),
    ]
    db.add_all(faculty_members)

    schedules = [
        Schedule(location_id=3,  course_code="CS-301", day_of_week=1, start_time=time(8, 0),  end_time=time(10, 0)),
        Schedule(location_id=3,  course_code="CS-401", day_of_week=1, start_time=time(10, 0), end_time=time(12, 0)),
        Schedule(location_id=4,  course_code="SE-201", day_of_week=1, start_time=time(9, 0),  end_time=time(11, 0)),
        Schedule(location_id=5,  course_code="CS-305", day_of_week=2, start_time=time(8, 0),  end_time=time(10, 0)),
        Schedule(location_id=7,  course_code="CS-499", day_of_week=3, start_time=time(14, 0), end_time=time(16, 0)),
        Schedule(location_id=11, course_code="IT-201", day_of_week=4, start_time=time(10, 0), end_time=time(12, 0)),
        Schedule(location_id=12, course_code="SE-401", day_of_week=5, start_time=time(8, 0),  end_time=time(10, 0)),
    ]
    db.add_all(schedules)
    db.commit()


def _seed_users(db) -> None:
    """Seed demo users for each role if none exist yet."""
    from app.auth_utils import hash_password

    if db.query(User).first() is not None:
        return

    users = [
        User(email="admin@pucit.edu.pk",   name="Admin",         password_hash=hash_password("Admin@123"),   role="admin"),
        User(email="teacher@pucit.edu.pk", name="Dr. Ahmed Khan",password_hash=hash_password("Teacher@123"), role="teacher"),
        User(email="teacher2@pucit.edu.pk",name="Dr. Sara Iqbal", password_hash=hash_password("Teacher@123"), role="teacher"),
        User(email="student1@pucit.edu.pk",name="Ali Raza",       password_hash=hash_password("Student@123"), role="student"),
        User(email="student2@pucit.edu.pk",name="Zara Ahmed",     password_hash=hash_password("Student@123"), role="student"),
        User(email="student3@pucit.edu.pk",name="Omar Sheikh",    password_hash=hash_password("Student@123"), role="student"),
        User(email="sac@pucit.edu.pk",     name="SAC Officer",    password_hash=hash_password("Sac@123"),     role="sac"),
        User(email="clerk@pucit.edu.pk",   name="Head Clerk",     password_hash=hash_password("Clerk@123"),   role="head_clerk"),
    ]
    db.add_all(users)
    db.commit()
    for u in users:
        db.refresh(u)

    # Map by email for convenience
    by_email = {u.email: u for u in users}
    teacher1 = by_email["teacher@pucit.edu.pk"]
    teacher2 = by_email["teacher2@pucit.edu.pk"]
    s1 = by_email["student1@pucit.edu.pk"]
    s2 = by_email["student2@pucit.edu.pk"]
    s3 = by_email["student3@pucit.edu.pk"]

    # Courses
    c1 = Course(code="CS-301", name="Data Structures", teacher_id=teacher1.user_id,
                section="A", semester="Fall 2024")
    c2 = Course(code="SE-201", name="Software Engineering", teacher_id=teacher2.user_id,
                section="B", semester="Fall 2024")
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)

    # Enrollments
    enrollments = [
        Enrollment(student_id=s1.user_id, course_id=c1.course_id),
        Enrollment(student_id=s2.user_id, course_id=c1.course_id),
        Enrollment(student_id=s3.user_id, course_id=c1.course_id),
        Enrollment(student_id=s1.user_id, course_id=c2.course_id),
        Enrollment(student_id=s2.user_id, course_id=c2.course_id),
    ]
    db.add_all(enrollments)
    db.commit()

    # Sample marks for CS-301
    marks = [
        # Attendance
        MarkRecord(student_id=s1.user_id, course_id=c1.course_id, category="attendance",
                   title="Attendance", marks_obtained=42, total_marks=45, uploaded_by=teacher1.user_id),
        MarkRecord(student_id=s2.user_id, course_id=c1.course_id, category="attendance",
                   title="Attendance", marks_obtained=38, total_marks=45, uploaded_by=teacher1.user_id),
        MarkRecord(student_id=s3.user_id, course_id=c1.course_id, category="attendance",
                   title="Attendance", marks_obtained=40, total_marks=45, uploaded_by=teacher1.user_id),
        # Quizzes
        MarkRecord(student_id=s1.user_id, course_id=c1.course_id, category="quiz",
                   title="Quiz 1", marks_obtained=8, total_marks=10, uploaded_by=teacher1.user_id),
        MarkRecord(student_id=s2.user_id, course_id=c1.course_id, category="quiz",
                   title="Quiz 1", marks_obtained=7, total_marks=10, uploaded_by=teacher1.user_id),
        MarkRecord(student_id=s3.user_id, course_id=c1.course_id, category="quiz",
                   title="Quiz 1", marks_obtained=9, total_marks=10, uploaded_by=teacher1.user_id),
        # Mid
        MarkRecord(student_id=s1.user_id, course_id=c1.course_id, category="mid",
                   title="Mid Exam", marks_obtained=24, total_marks=30, uploaded_by=teacher1.user_id),
        MarkRecord(student_id=s2.user_id, course_id=c1.course_id, category="mid",
                   title="Mid Exam", marks_obtained=21, total_marks=30, uploaded_by=teacher1.user_id),
        MarkRecord(student_id=s3.user_id, course_id=c1.course_id, category="mid",
                   title="Mid Exam", marks_obtained=26, total_marks=30, uploaded_by=teacher1.user_id),
    ]
    db.add_all(marks)
    db.commit()


def init_db() -> None:
    """Create all tables and seed with sample data."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_locations(db)
        _seed_users(db)
    finally:
        db.close()


def get_db():
    """FastAPI dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
