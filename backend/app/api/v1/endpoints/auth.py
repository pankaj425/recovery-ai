from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DBSession, CurrentUser
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DBSession) -> TokenResponse:
    result = auth_service.login(db, payload.email, payload.password)
    return TokenResponse(**result)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
