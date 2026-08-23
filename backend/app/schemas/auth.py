from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: str = Field(examples=["merchant@recovery.ai"])
    password: str = Field(min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: "UserOut"


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    role: str

