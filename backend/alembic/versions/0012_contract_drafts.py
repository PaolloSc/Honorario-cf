"""rascunhos do wizard (autosave no servidor)

Revision ID: 0012_contract_drafts
Revises: 0011_drop_colaboradores_areas
Create Date: 2026-10-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_contract_drafts"
down_revision = "0011_drop_colaboradores_areas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # O app cria as tabelas novas sozinho na subida (init_db → create_all): se o deploy
    # veio antes desta migração, a tabela já existe e não há o que fazer.
    if sa.inspect(op.get_bind()).has_table("contract_drafts"):
        return
    op.create_table(
        "contract_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("draft_id", sa.String(64), nullable=False),
        sa.Column("owner_email", sa.String(256), nullable=False),
        sa.Column("client_name", sa.String(256), nullable=False, server_default=""),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("form_data_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contract_drafts_draft_id", "contract_drafts", ["draft_id"], unique=True)
    op.create_index("ix_contract_drafts_owner_email", "contract_drafts", ["owner_email"])


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("contract_drafts"):
        return
    op.drop_index("ix_contract_drafts_owner_email", table_name="contract_drafts")
    op.drop_index("ix_contract_drafts_draft_id", table_name="contract_drafts")
    op.drop_table("contract_drafts")
