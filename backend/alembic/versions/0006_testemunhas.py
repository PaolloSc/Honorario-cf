"""roster de testemunhas recorrentes do escritorio

Revision ID: 0006_testemunhas
Revises: 0005_tax_codes_sap_like
Create Date: 2026-05-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0006_testemunhas"
down_revision = "0005_tax_codes_sap_like"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "testemunhas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(256), nullable=False),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_testemunhas_email", "testemunhas", ["email"])


def downgrade() -> None:
    op.drop_index("idx_testemunhas_email", table_name="testemunhas")
    op.drop_table("testemunhas")
