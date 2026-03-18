"""Shared pytest fixtures for the SCNRO backend test suite.

Uses an in-memory SQLite database so no external PostgreSQL is required.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.models import Base, Faculty, ItemLostFound, Location, Schedule
from app.main import app

SQLITE_URL = "sqlite:///./test_scnro.db"

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables():
    """Truncate all tables before each test."""
    db = TestingSessionLocal()
    db.query(ItemLostFound).delete()
    db.query(Schedule).delete()
    db.query(Faculty).delete()
    db.query(Location).delete()
    db.commit()
    db.close()


@pytest.fixture
def db():
    database = TestingSessionLocal()
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def client(db, monkeypatch):
    # Prevent the lifespan handler from trying to connect to PostgreSQL.
    # Patch 'init_db' in app.main's namespace (imported via `from app.database import init_db`).
    import app.main as _main_module

    monkeypatch.setattr(_main_module, "init_db", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_location(db, **kwargs) -> Location:
    defaults = dict(
        name="Test Room",
        category="Classroom",
        wing_name="Old Campus",
        floor_level=1,
        latitude=31.48260,
        longitude=74.30360,
        is_active=True,
    )
    defaults.update(kwargs)
    loc = Location(**defaults)
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


def make_schedule(db, location_id: int, **kwargs) -> Schedule:
    from datetime import time

    defaults = dict(
        location_id=location_id,
        course_code="CS-101",
        day_of_week=1,
        start_time=time(10, 0),
        end_time=time(12, 0),
    )
    defaults.update(kwargs)
    sched = Schedule(**defaults)
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


def make_faculty(db, **kwargs) -> Faculty:
    defaults = dict(
        name="Dr. Test",
        designation="Professor",
        department="CS",
        is_available=True,
    )
    defaults.update(kwargs)
    fac = Faculty(**defaults)
    db.add(fac)
    db.commit()
    db.refresh(fac)
    return fac
