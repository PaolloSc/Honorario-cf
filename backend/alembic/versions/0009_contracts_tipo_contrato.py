"""contracts tipo_contrato

A lista de contratos mistura honorarios e Acao de Consumo sem indicar qual e'
qual — usuario clica "Editar" num e cai no wizard errado. Persiste o tipo pra
lista poder mostrar um badge e evitar a surpresa.

Revision ID: 0009_contracts_tipo_contrato
Revises: 0008_legalone_opcoes
Create Date: 2026-09-02
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0009_contracts_tipo_contrato"
down_revision = "0008_legalone_opcoes"
branch_labels = None
depends_on = None

TIPO_HONORARIOS = "honorarios"
TIPO_CONSUMIDOR_AEREO = "consumidor_aereo"


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("tipo_contrato", sa.String(32), nullable=False, server_default=TIPO_HONORARIOS),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT c.contract_id, v.form_data_json
            FROM contracts c
            JOIN contract_versions v ON v.contract_id = c.contract_id
            WHERE v.version_number = c.current_version
            """
        )
    ).fetchall()

    for contract_id, form_json in rows:
        try:
            data = json.loads(form_json or "{}")
        except Exception:
            continue
        if data.get("tipo_contrato") == TIPO_CONSUMIDOR_AEREO:
            conn.execute(
                sa.text("UPDATE contracts SET tipo_contrato = :tipo WHERE contract_id = :cid"),
                {"tipo": TIPO_CONSUMIDOR_AEREO, "cid": contract_id},
            )


def downgrade() -> None:
    op.drop_column("contracts", "tipo_contrato")
