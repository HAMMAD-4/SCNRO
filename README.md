# SCNRO — Smart Campus Navigation & Resource Optimizer

The SCNRO system is a mobile-first application designed to optimize the daily
life of students and faculty at PUCIT.  It focuses on real-time spatial
awareness and resource allocation that traditional CMS systems ignore.

---

## Architecture

```
┌─────────────────────┐      HTTP/REST      ┌─────────────────────────┐
│  Flutter Mobile App │ ◄──────────────────► │  FastAPI Python Backend │
│  (Presentation)     │                      │  (Application Layer)    │
└─────────────────────┘                      └────────────┬────────────┘
                                                          │
                                              ┌───────────┴───────────┐
                                              │  PostgreSQL + Redis    │
                                              │  (Data Layer)         │
                                              └───────────────────────┘
```

| Layer        | Technology                                |
|-------------|-------------------------------------------|
| Mobile App  | Flutter 3 · Provider · flutter_map        |
| Backend     | FastAPI (Python 3.11) · Uvicorn            |
| AI/Routing  | NetworkX (Dijkstra) · Haversine formula    |
| Database    | PostgreSQL 15 + PostGIS · SQLAlchemy 2     |
| Cache       | Redis 7                                   |
| Container   | Docker + docker-compose                   |

---

## Features

| ID   | Feature              | Description                                                                 |
|------|----------------------|-----------------------------------------------------------------------------|
| FR-1 | Indoor Navigation    | Shortest-path routing via Dijkstra's algorithm on a campus node-graph.      |
| FR-2 | Live Space Finder    | Identifies vacant classrooms / labs based on the current timetable.         |
| FR-3 | Faculty Locator      | Searchable faculty database with "Navigate to Office" button.               |
| FR-4 | Lost & Found         | Community board — report, browse, and claim lost/found items.               |
| FR-5 | AI Optimizer         | Ranks study spots by proximity (Haversine) and remaining free-window size.  |

---

## API Endpoints

| Method | Endpoint                          | Description                                   |
|--------|-----------------------------------|-----------------------------------------------|
| GET    | `/api/v1/navigate?to={room_id}`   | Shortest indoor path (node list + coordinates)|
| GET    | `/api/v1/resources/available`     | Ranked list of currently vacant rooms         |
| POST   | `/api/v1/items/report`            | Report a lost or found item                   |
| GET    | `/api/v1/items`                   | List community lost & found items             |
| PATCH  | `/api/v1/items/{id}/claim`        | Mark an item as claimed                       |
| GET    | `/api/v1/faculty/search?name=…`   | Search faculty by name                        |
| GET    | `/api/v1/faculty/{id}`            | Get a faculty member's details                |
| GET    | `/health`                         | Liveness probe                                |

Interactive Swagger UI is available at `http://localhost:8000/docs` once the
backend is running.

---

## Quick Start (Docker)

> **Prerequisites:** Docker ≥ 24 and Docker Compose v2.

```bash
# Clone the repo
git clone https://github.com/HAMMAD-4/SCNRO.git
cd SCNRO

# Start all services (PostgreSQL + Redis + FastAPI backend)
docker compose up --build
```

The API will be available at **http://localhost:8000**.  
The database is seeded automatically by the SQL files in `database/migrations/`.

---

## Backend — Local Development

```bash
cd backend

# Create a virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://scnro_user:scnro_pass@localhost:5432/scnro_db"
export REDIS_URL="redis://localhost:6379/0"

# Run the dev server
uvicorn app.main:app --reload --port 8000
```

### Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

All tests use an in-memory **SQLite** database — no PostgreSQL or Redis
required to run the test suite.

---

## Flutter Frontend

```bash
cd frontend

# Get dependencies
flutter pub get

# Run on an Android emulator (the API base URL defaults to 10.0.2.2:8000)
flutter run

# Pass a custom API URL at build time
flutter run --dart-define=API_BASE_URL=http://192.168.1.5:8000
```

---

## Project Structure

```
SCNRO/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application & lifespan
│   │   ├── database.py          # SQLAlchemy engine + session factory
│   │   ├── models.py            # ORM models (Location, Schedule, Faculty, …)
│   │   ├── routers/
│   │   │   ├── navigation.py    # GET /api/v1/navigate
│   │   │   ├── resources.py     # GET /api/v1/resources/available
│   │   │   ├── lost_found.py    # POST /api/v1/items/report, GET /api/v1/items
│   │   │   └── faculty.py       # GET /api/v1/faculty/search
│   │   └── services/
│   │       └── optimizer.py     # Haversine + Dijkstra AI optimizer
│   ├── tests/
│   │   ├── conftest.py          # SQLite fixtures & test client
│   │   ├── test_api.py          # API endpoint tests (33 tests)
│   │   └── test_optimizer.py    # Optimizer unit tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── lib/
│   │   ├── main.dart            # App entry point + Provider setup
│   │   ├── models/models.dart   # Dart data classes
│   │   ├── services/api_service.dart  # HTTP client wrapper
│   │   ├── providers/providers.dart   # ChangeNotifier state management
│   │   └── screens/
│   │       ├── dashboard_screen.dart  # Home / Live Campus Updates
│   │       ├── map_screen.dart        # flutter_map with route polyline
│   │       ├── lost_found_screen.dart # Community board
│   │       └── faculty_screen.dart    # Faculty search & navigate
│   └── pubspec.yaml
├── database/
│   └── migrations/
│       ├── 001_initial_schema.sql   # Table definitions
│       └── 002_seed_data.sql        # Sample PUCIT data
└── docker-compose.yml
```

