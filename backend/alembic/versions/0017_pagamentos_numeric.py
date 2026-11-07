"""participacao_pagamentos: dinheiro de Float para Numeric(14,2)

Valores em Float acumulam erro de centavo; Numeric guarda exato. Pronta no PR e NAO
aplicada em producao sem o ok do Paollo (fazer backup do Neon antes). Cada valor e'
arredondado a 2 casas na conversao (Postgres: USING round(col::numeric, 2)).

Revision ID: 0017_pagamentos_numeric
Revises: 0016_colaboradores_oabs
Create Date: 2026-11-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_pagamentos_numeric"
down_revision = "0016_colaboradores_oabs"
branch_labels = None
depends_on = None

COLUNAS = ("valor_liquido_recebido", "valor_participacao", "valor_bruto", "imposto_total")


def _converter(de: sa.types.TypeEngine, para: sa.types.TypeEngine, usando: str) -> None:
    pg = op.get_bind().dialect.name == "postgresql"
    with op.batch_alter_table("participacao_pagamentos") as batch:
        for col in COLUNAS:
            batch.alter_column(
                col,
                existing_type=de,
                type_=para,
                postgresql_using=usando.format(col=col) if pg else None,
            )


def upgrade() -> None:
    _converter(sa.Float(), sa.Numeric(14, 2), "round({col}::numeric, 2)")


def downgrade() -> None:
    _converter(sa.Numeric(14, 2), sa.Float(), "{col}::double precision")
