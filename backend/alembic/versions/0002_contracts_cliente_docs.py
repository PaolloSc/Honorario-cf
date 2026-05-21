"""contracts cliente_docs

Revision ID: 0002_contracts_cliente_docs
Revises: 0001_nfse_tables
Create Date: 2026-05-20
"""
from __future__ import annotations

import json
import re

import sqlalchemy as sa
from alembic import op


revision = "0002_contracts_cliente_docs"
down_revision = "0001_nfse_tables"
branch_labels = None
depends_on = None


def _only_digits(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\D", "", s)


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("cliente_docs", sa.Text, nullable=False, server_default="[]"),
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
        docs: set[str] = set()
        try:
            data = json.loads(form_json or "{}")
            for contratante in data.get("contratantes", []) or []:
                doc = _only_digits(contratante.get("cnpj") or contratante.get("cpf"))
                if doc:
                    docs.add(doc)
        except Exception:
            continue
        conn.execute(
            sa.text("UPDATE contracts SET cliente_docs = :docs WHERE contract_id = :cid"),
            {"docs": json.dumps(sorted(docs)), "cid": contract_id},
        )


def downgrade() -> None:
    op.drop_column("contracts", "cliente_docs")
