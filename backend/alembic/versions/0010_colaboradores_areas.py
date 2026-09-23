"""colaboradores areas

Cada socio responde por areas (Cível, Trabalhista, Tributário...): o wizard
sugere esse socio para assinar pelo escritorio nos contratos da area.

Revision ID: 0010_colaboradores_areas
Revises: 0009_contracts_tipo_contrato
Create Date: 2026-09-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_colaboradores_areas"
down_revision = "0009_contracts_tipo_contrato"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("colaboradores", sa.Column("areas", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("colaboradores", "areas")
