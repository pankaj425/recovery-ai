"""Authentication service + FastAPI dependency."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user and user.is_active and verify_password(password, user.password_hash):
        return user
    return None


def login(db: Session, email: str, password: str) -> dict:
    user = authenticate(db, email, password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}},
        )
    token = create_access_token(subject=user.email, role=user.role)
    from app.core.config import settings

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": settings.access_token_expire_minutes,
        "user": user,
    }


def ensure_demo_user(db: Session) -> User:
    """Idempotently provision the demo merchant account (dev convenience)."""
    from app.core.config import settings

    user = db.scalar(select(User).where(User.email == settings.demo_user_email))
    if user is None:
        user = User(
            name="Demo Merchant",
            email=settings.demo_user_email,
            role="merchant",
            password_hash=hash_password(settings.demo_user_password),
        )
        db.add(user)
        db.commit()
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"success": False, "error": {"code": "UNAUTHENTICATED", "message": "Missing or invalid bearer token"}},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise unauthorized from None
    email = payload.get("sub")
    user = db.scalar(select(User).where(User.email == email)) if email else None
    if user is None or not user.is_active:
        raise unauthorized
    return user
