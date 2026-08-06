"""opcoes das tabelas do Legal One (categoria de cliente, etiqueta, lista de transmissao)

Revision ID: 0008_legalone_opcoes
Revises: 0007_colaboradores
Create Date: 2026-08-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0008_legalone_opcoes"
down_revision = "0007_colaboradores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legalone_opcoes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tipo", sa.String(32), nullable=False),
        sa.Column("valor", sa.String(256), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tipo", "valor", name="uq_legalone_opcao"),
    )


def downgrade() -> None:
    op.drop_table("legalone_opcoes")
