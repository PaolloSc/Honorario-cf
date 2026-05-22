"""pagamento parcelamento (parcela_num/parcela_total/nf_referencia)

Revision ID: 0004_pagamento_parcelamento
Revises: 0003_pagamento_status
Create Date: 2026-05-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0004_pagamento_parcelamento"
down_revision = "0003_pagamento_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "participacao_pagamentos",
        sa.Column("parcela_num", sa.Integer, nullable=False, server_default="1"),
    )
    op.add_column(
        "participacao_pagamentos",
        sa.Column("parcela_total", sa.Integer, nullable=False, server_default="1"),
    )
    op.add_column(
        "participacao_pagamentos",
        sa.Column("nf_referencia", sa.String(64), nullable=True),
    )
    op.create_index(
        "idx_participacao_pagamentos_nf",
        "participacao_pagamentos",
        ["nf_referencia"],
    )


def downgrade() -> None:
    op.drop_index("idx_participacao_pagamentos_nf", table_name="participacao_pagamentos")
    op.drop_column("participacao_pagamentos", "nf_referencia")
    op.drop_column("participacao_pagamentos", "parcela_total")
    op.drop_column("participacao_pagamentos", "parcela_num")
