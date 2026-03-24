"""Smart Campus Navigation & Resource Optimizer — FastAPI backend."""

from __future__ import annotations

import os
import sys

# Allow `python main.py` to be run directly from the backend/app directory by
# ensuring the backend root (parent of this file's directory) is on sys.path
# so that `from app.*` imports resolve correctly.
if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import navigation, resources, lost_found, faculty
from app.routers import auth as auth_router
from app.routers import admin as admin_router
from app.routers import marks as marks_router
from app.routers import clerk as clerk_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database tables on first launch."""
    init_db()
    yield


app = FastAPI(
    title="SCNRO – Smart Campus Navigation & Resource Optimizer",
    description=(
        "Backend API for the SCNRO mobile application. "
        "Provides indoor navigation, live room availability, "
        "a community lost-and-found board, and a faculty locator."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Allow Flutter dev builds and web preview to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(navigation.router)
app.include_router(resources.router)
app.include_router(lost_found.router)
app.include_router(faculty.router)
app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(marks_router.router)
app.include_router(clerk_router.router)


@app.get("/health", tags=["Health"])
def health_check():
    """Quick liveness probe used by load-balancers / CI pipelines."""
    return {"status": "ok", "service": "SCNRO Backend"}


# Serve the web UI -------------------------------------------------------
_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def serve_ui():
        """Serve the single-page web app at the root URL."""
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
