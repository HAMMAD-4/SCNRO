-- SCNRO Seed Data
-- Populate the database with representative PUCIT campus data for development.
-- Run after 001_initial_schema.sql

-- ---------------------------------------------------------------------------
-- Locations — PUCIT Old Campus & New Campus
-- ---------------------------------------------------------------------------
INSERT INTO locations (name, category, wing_name, floor_level, latitude, longitude) VALUES
  ('Main Entrance',        'Corridor',   'Old Campus', 0,  31.48260, 74.30360),
  ('CS Block Corridor',    'Corridor',   'Old Campus', 1,  31.48270, 74.30370),
  ('Computer Lab 1',       'Lab',        'Old Campus', 1,  31.48280, 74.30375),
  ('Computer Lab 2',       'Lab',        'Old Campus', 1,  31.48285, 74.30380),
  ('Computer Lab 3',       'Lab',        'Old Campus', 2,  31.48290, 74.30385),
  ('Computer Lab 4',       'Lab',        'New Campus', 1,  31.48295, 74.30390),
  ('Seminar Hall',         'Classroom',  'Old Campus', 1,  31.48265, 74.30365),
  ('Faculty Block',        'Corridor',   'Old Campus', 2,  31.48300, 74.30395),
  ('Dean Office',          'Office',     'Old Campus', 2,  31.48310, 74.30400),
  ('Cafeteria',            'Cafe',       'Old Campus', 0,  31.48250, 74.30355),
  ('Lecture Hall A',       'Classroom',  'New Campus', 1,  31.48315, 74.30405),
  ('Lecture Hall B',       'Classroom',  'New Campus', 2,  31.48320, 74.30410),
  ('Library',              'Classroom',  'Old Campus', 1,  31.48245, 74.30350),
  ('Project Room 1',       'Lab',        'New Campus', 2,  31.48325, 74.30415),
  ('Project Room 2',       'Lab',        'New Campus', 2,  31.48330, 74.30420)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- Faculty
-- ---------------------------------------------------------------------------
INSERT INTO faculty (name, designation, department, office_location_id, is_available) VALUES
  ('Dr. Ahmed Khan',    'Professor',        'Computer Science',          9,  TRUE),
  ('Dr. Sara Iqbal',    'Associate Professor','Software Engineering',    8,  TRUE),
  ('Mr. Bilal Hussain', 'Lecturer',         'Computer Science',          8,  FALSE),
  ('Ms. Fatima Malik',  'Lecturer',         'Information Technology',    8,  TRUE)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- Schedules (Monday = 1, current semester sample)
-- ---------------------------------------------------------------------------
INSERT INTO schedules (location_id, course_code, day_of_week, start_time, end_time) VALUES
  -- Lab 1: Monday 08:00–10:00
  (3, 'CS-301', 1, '08:00', '10:00'),
  -- Lab 1: Monday 10:00–12:00
  (3, 'CS-401', 1, '10:00', '12:00'),
  -- Lab 2: Monday 09:00–11:00
  (4, 'SE-201', 1, '09:00', '11:00'),
  -- Lab 3: Tuesday 08:00–10:00
  (5, 'CS-305', 2, '08:00', '10:00'),
  -- Seminar Hall: Wednesday 14:00–16:00
  (7, 'CS-499', 3, '14:00', '16:00'),
  -- Lecture Hall A: Thursday 10:00–12:00
  (11,'IT-201', 4, '10:00', '12:00'),
  -- Lecture Hall B: Friday 08:00–10:00
  (12,'SE-401', 5, '08:00', '10:00')
ON CONFLICT DO NOTHING;
