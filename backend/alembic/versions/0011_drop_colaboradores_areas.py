"""drop colaboradores areas

Reverte a 0010: a feature de "área do contrato" (sócio responsável por
área) foi removida — nunca chegou a ter uma área cadastrada pelo escritório.

Revision ID: 0011_drop_colaboradores_areas
Revises: 0010_colaboradores_areas
Create Date: 2026-09-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_drop_colaboradores_areas"
down_revision = "0010_colaboradores_areas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("colaboradores", "areas")


def downgrade() -> None:
    op.add_column("colaboradores", sa.Column("areas", sa.String(512), nullable=True))
