"""pagamento status workflow (a_receber/aguardando_pagamento/pago)

Revision ID: 0003_pagamento_status
Revises: 0002_contracts_cliente_docs
Create Date: 2026-05-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0003_pagamento_status"
down_revision = "0002_contracts_cliente_docs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rows existentes vieram de fluxo antigo (pagamento confirmado) -> default 'pago'
    op.add_column(
        "participacao_pagamentos",
        sa.Column("status", sa.String(32), nullable=False, server_default="pago"),
    )
    op.create_index(
        "idx_participacao_pagamentos_status",
        "participacao_pagamentos",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("idx_participacao_pagamentos_status", table_name="participacao_pagamentos")
    op.drop_column("participacao_pagamentos", "status")
