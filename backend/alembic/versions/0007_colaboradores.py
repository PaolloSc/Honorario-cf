"""roster interno de colaboradores (advogados/socios/etc.)

Revision ID: 0007_colaboradores
Revises: 0006_testemunhas
Create Date: 2026-05-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0007_colaboradores"
down_revision = "0006_testemunhas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "colaboradores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(256), nullable=False),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("papel", sa.String(32), nullable=False, server_default="advogado"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_colaboradores_nome", "colaboradores", ["nome"])
    op.create_index("idx_colaboradores_papel", "colaboradores", ["papel"])


def downgrade() -> None:
    op.drop_index("idx_colaboradores_papel", table_name="colaboradores")
    op.drop_index("idx_colaboradores_nome", table_name="colaboradores")
    op.drop_table("colaboradores")
