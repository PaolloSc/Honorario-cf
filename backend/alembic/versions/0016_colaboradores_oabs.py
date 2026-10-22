"""colaboradores.oabs

OABs do advogado (JSON [{"numero", "uf"}]), usadas para preencher o substabelecimento.

Revision ID: 0016_colaboradores_oabs
Revises: 0015_documentos_complementares
Create Date: 2026-10-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_colaboradores_oabs"
down_revision = "0015_documentos_complementares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("colaboradores", sa.Column("oabs", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("colaboradores", "oabs")
