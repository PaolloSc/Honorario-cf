"""tax_codes master data + cols SAP-like em participacao_pagamentos

Revision ID: 0005_tax_codes_sap_like
Revises: 0004_pagamento_parcelamento
Create Date: 2026-05-22
"""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0005_tax_codes_sap_like"
down_revision = "0004_pagamento_parcelamento"
branch_labels = None
depends_on = None

ALIQUOTA_PADRAO = 0.1545
SEED_ISS = 0.0
SEED_PIS = 0.0065
SEED_COFINS = 0.03
SEED_IRRF = 0.015
SEED_CSLL = 0.01


def upgrade() -> None:
    # 1. tabela tax_codes
    op.create_table(
        "tax_codes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("codigo", sa.String(32), nullable=False, unique=True),
        sa.Column("descricao", sa.String(256), nullable=False),
        sa.Column("aliquota_total", sa.Numeric(5, 4), nullable=False),
        sa.Column("aliquota_iss", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("aliquota_pis", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("aliquota_cofins", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("aliquota_irrf", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("aliquota_csll", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("criado_por", sa.String(256), nullable=False),
    )
    op.create_index("idx_tax_codes_codigo", "tax_codes", ["codigo"], unique=True)

    # 2. seed PADRAO_1545
    op.execute(
        sa.text(
            """
            INSERT INTO tax_codes
              (codigo, descricao, aliquota_total, aliquota_iss, aliquota_pis,
               aliquota_cofins, aliquota_irrf, aliquota_csll, ativo, criado_em, criado_por)
            VALUES
              (:codigo, :descricao, :total, :iss, :pis, :cofins, :irrf, :csll, 1, :now, 'sistema')
            """
        ).bindparams(
            codigo="PADRAO_1545",
            descricao="Retencoes federais agregadas (PIS+COFINS+IRRF+CSLL)",
            total=ALIQUOTA_PADRAO,
            iss=SEED_ISS,
            pis=SEED_PIS,
            cofins=SEED_COFINS,
            irrf=SEED_IRRF,
            csll=SEED_CSLL,
            now=datetime.now(timezone.utc),
        )
    )

    # 3. cols novas em participacao_pagamentos
    # FK constraint nao usa op.add_column com ForeignKey direto (SQLite nao suporta ALTER ADD CONSTRAINT).
    # FK eh enforced em runtime pelo SQLAlchemy via model declaration; em Postgres a constraint pode ser
    # adicionada separadamente se necessario.
    op.add_column(
        "participacao_pagamentos",
        sa.Column("tax_code_id", sa.Integer, nullable=True),
    )
    op.add_column("participacao_pagamentos", sa.Column("valor_bruto", sa.Float, nullable=True))
    op.add_column(
        "participacao_pagamentos",
        sa.Column("imposto_total", sa.Float, nullable=False, server_default="0"),
    )
    op.add_column("participacao_pagamentos", sa.Column("tipo_cobranca", sa.String(32), nullable=True))
    op.add_column(
        "participacao_pagamentos",
        sa.Column("natureza_pagamento", sa.String(32), nullable=True),
    )
    op.add_column(
        "participacao_pagamentos",
        sa.Column("tipo_documento", sa.String(32), nullable=False, server_default="nf"),
    )
    op.create_index(
        "idx_pagamento_natureza", "participacao_pagamentos", ["natureza_pagamento"]
    )
    op.create_index(
        "idx_pagamento_tax_code", "participacao_pagamentos", ["tax_code_id"]
    )

    # 4. backfill
    conn = op.get_bind()
    seed_id = conn.execute(
        sa.text("SELECT id FROM tax_codes WHERE codigo='PADRAO_1545'")
    ).scalar_one()

    conn.execute(
        sa.text(
            """
            UPDATE participacao_pagamentos
            SET tax_code_id = :seed_id,
                tipo_documento = 'nf'
            WHERE tax_code_id IS NULL
            """
        ),
        {"seed_id": seed_id},
    )

    conn.execute(
        sa.text(
            """
            UPDATE participacao_pagamentos
            SET valor_bruto = ROUND(valor_liquido_recebido / (1 - :aliq), 2),
                imposto_total = ROUND(valor_liquido_recebido / (1 - :aliq) - valor_liquido_recebido, 2)
            WHERE valor_bruto IS NULL
            """
        ),
        {"aliq": ALIQUOTA_PADRAO},
    )

    # tipo_cobranca herdado de participacoes.tipo_honorario
    conn.execute(
        sa.text(
            """
            UPDATE participacao_pagamentos
            SET tipo_cobranca = (
                SELECT p.tipo_honorario FROM participacoes p
                WHERE p.id = participacao_pagamentos.participacao_id
            )
            WHERE tipo_cobranca IS NULL
            """
        )
    )

    # natureza_pagamento inferida dos pcts
    conn.execute(
        sa.text(
            """
            UPDATE participacao_pagamentos
            SET natureza_pagamento = (
                SELECT CASE
                    WHEN p.percentual_captacao > 0 AND p.percentual_performance > 0 THEN 'captacao_performance'
                    WHEN p.percentual_performance > 0 THEN 'performance'
                    ELSE 'captacao'
                END
                FROM participacoes p WHERE p.id = participacao_pagamentos.participacao_id
            )
            WHERE natureza_pagamento IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_pagamento_tax_code", table_name="participacao_pagamentos")
    op.drop_index("idx_pagamento_natureza", table_name="participacao_pagamentos")
    op.drop_column("participacao_pagamentos", "tipo_documento")
    op.drop_column("participacao_pagamentos", "natureza_pagamento")
    op.drop_column("participacao_pagamentos", "tipo_cobranca")
    op.drop_column("participacao_pagamentos", "imposto_total")
    op.drop_column("participacao_pagamentos", "valor_bruto")
    op.drop_column("participacao_pagamentos", "tax_code_id")
    op.drop_index("idx_tax_codes_codigo", table_name="tax_codes")
    op.drop_table("tax_codes")
