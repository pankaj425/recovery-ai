"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db as _db_dependency
from app.models import User
from app.services.auth_service import get_current_user as _auth_dependency


def _current(user: User = Depends(_auth_dependency)) -> User:
    return user


DBSession = Annotated[Session, Depends(_db_dependency)]
CurrentUser = Annotated[User, Depends(_current)]
