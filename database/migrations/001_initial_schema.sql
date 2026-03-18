-- SCNRO Database Schema
-- Run against a PostgreSQL instance with the PostGIS extension available.
-- Usage: psql -U scnro_user -d scnro_db -f 001_initial_schema.sql

-- ---------------------------------------------------------------------------
-- Core Table for Campus Locations
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS locations (
    location_id SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    category    VARCHAR(50),            -- 'Lab', 'Classroom', 'Office', 'Cafe'
    wing_name   VARCHAR(50),            -- 'Old Campus', 'New Campus'
    floor_level INT,
    latitude    DECIMAL(10, 8),
    longitude   DECIMAL(11, 8),
    is_active   BOOLEAN DEFAULT TRUE
);

-- ---------------------------------------------------------------------------
-- Schedule Table for Resource Optimization
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id SERIAL PRIMARY KEY,
    location_id INT REFERENCES locations(location_id) ON DELETE CASCADE,
    course_code VARCHAR(20),
    day_of_week INT,   -- 1 (Mon) to 7 (Sun)
    start_time  TIME,
    end_time    TIME
);

-- ---------------------------------------------------------------------------
-- Faculty Table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS faculty (
    faculty_id         SERIAL PRIMARY KEY,
    name               VARCHAR(255) NOT NULL,
    designation        VARCHAR(100),
    department         VARCHAR(100),
    office_location_id INT REFERENCES locations(location_id) ON DELETE SET NULL,
    is_available       BOOLEAN DEFAULT TRUE
);

-- ---------------------------------------------------------------------------
-- Lost and Found Module
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items_lost_found (
    item_id           SERIAL PRIMARY KEY,
    user_id           INT,              -- Link to external User Table
    item_name         VARCHAR(100),
    description       TEXT,
    image_url         VARCHAR(255),
    status            VARCHAR(20),      -- 'Lost', 'Found', 'Claimed'
    location_last_seen INT REFERENCES locations(location_id) ON DELETE SET NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Useful indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_schedules_location_day
    ON schedules (location_id, day_of_week);

CREATE INDEX IF NOT EXISTS idx_schedules_time_range
    ON schedules (day_of_week, start_time, end_time);

CREATE INDEX IF NOT EXISTS idx_items_status
    ON items_lost_found (status);

CREATE INDEX IF NOT EXISTS idx_faculty_name
    ON faculty (name);
