"""contracts contrato_origem_id

Aditivo, distrato e substabelecimento (issue #126) sao contratos derivados de um
contrato de origem. Coluna anulavel: o substabelecimento pode nascer sem origem.

Revision ID: 0015_documentos_complementares
Revises: 0014_emissao_nfse
Create Date: 2026-10-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_documentos_complementares"
down_revision = "0014_emissao_nfse"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("contrato_origem_id", sa.String(64), sa.ForeignKey("contracts.contract_id"), nullable=True),
    )
    op.create_index("ix_contracts_contrato_origem_id", "contracts", ["contrato_origem_id"])


def downgrade() -> None:
    op.drop_index("ix_contracts_contrato_origem_id", table_name="contracts")
    op.drop_column("contracts", "contrato_origem_id")
