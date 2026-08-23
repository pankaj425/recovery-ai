"""initial schema - all RecoveryAI tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-23

Baseline migration: creates the full schema from the SQLAlchemy metadata.
Future revisions should use explicit op.add_column / op.create_table calls.
"""
from __future__ import annotations

from alembic import op

from app.core.database import Base
import app.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
