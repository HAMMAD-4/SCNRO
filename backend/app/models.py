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
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


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

    location = relationship("Location", back_populates="schedules")


class ItemLostFound(Base):
    """Community lost-and-found board entry."""

    __tablename__ = "items_lost_found"

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    item_name = Column(String(100))
    description = Column(Text)
    image_url = Column(String(255))
    status = Column(String(20))  # 'Lost', 'Found', 'Claimed'
    location_last_seen = Column(Integer, ForeignKey("locations.location_id"))
    created_at = Column(TIMESTAMP, server_default=func.now())

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
