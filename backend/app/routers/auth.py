"""Auth router — login, signup-request, /me"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth_utils import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import SignupRequest, User

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

ALLOWED_SELF_ROLES = {"teacher", "student", "sac", "head_clerk"}


# ── Schemas ─────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequestCreate(BaseModel):
    email: str = Field(..., description="University email address")
    name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=6)
    role: str = Field(..., description="teacher | student | sac | head_clerk")


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email + password; returns a JWT access token."""
    user = db.query(User).filter(
        User.email == payload.email.lower().strip(),
        User.is_active == True,  # noqa: E712
    ).first()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        name=user.name,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


@router.post("/signup-request", status_code=201)
def signup_request(payload: SignupRequestCreate, db: Session = Depends(get_db)):
    """Submit a signup request for admin approval.

    - Only university-domain requests are accepted.
    - Duplicate emails (already a user or pending request) are rejected.
    - Admin role cannot be self-requested.
    """
    email = payload.email.lower().strip()

    if payload.role not in ALLOWED_SELF_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of: {', '.join(sorted(ALLOWED_SELF_ROLES))}",
        )

    # Reject if email already has a user account
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409,
                            detail="An account with this email already exists.")

    # Reject duplicate pending request
    existing = db.query(SignupRequest).filter(
        SignupRequest.email == email,
        SignupRequest.status == "pending",
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A pending signup request for this email already exists.",
        )

    req = SignupRequest(
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role_requested=payload.role,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {
        "message": "Signup request submitted. Awaiting admin approval.",
        "request_id": req.request_id,
        "email": req.email,
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
    }
