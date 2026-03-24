import os
from datetime import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Faculty, Location, Schedule

DATABASE_URL = os.getenv(
    "DATABASE_URL",
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


def _seed(db) -> None:
    """Insert sample PUCIT data if the database is empty."""
    if db.query(Location).count() > 0:
        return  # already seeded

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


def init_db() -> None:
    """Create all tables and seed with sample data."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()


def get_db():
    """FastAPI dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
