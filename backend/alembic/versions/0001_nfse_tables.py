"""nfse tables

Revision ID: 0001_nfse_tables
Revises:
Create Date: 2026-05-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0001_nfse_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credencial_pbh",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cnpj_prestador", sa.String(14), nullable=False, unique=True),
        sa.Column("login_enc", sa.LargeBinary, nullable=False),
        sa.Column("senha_enc", sa.LargeBinary, nullable=False),
        sa.Column("nonce_login", sa.LargeBinary, nullable=False),
        sa.Column("nonce_senha", sa.LargeBinary, nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("motivo_inativacao", sa.Text, nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("criado_por", sa.String(255), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "nfse_recebidas",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cnpj_prestador", sa.String(14), nullable=False),
        sa.Column("numero", sa.String(40), nullable=False),
        sa.Column("serie", sa.String(10), nullable=True),
        sa.Column("codigo_verificacao", sa.String(40), nullable=True),
        sa.Column("competencia", sa.Date, nullable=False),
        sa.Column("data_emissao", sa.Date, nullable=False),
        sa.Column("tomador_doc", sa.String(14), nullable=False),
        sa.Column("tomador_nome", sa.Text, nullable=True),
        sa.Column("valor_servicos", sa.Numeric(12, 2), nullable=False),
        sa.Column("iss_retido", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("irrf", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("pis", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cofins", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("csll", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("valor_liquido", sa.Numeric(12, 2), nullable=False),
        sa.Column("discriminacao", sa.Text, nullable=True),
        sa.Column("cancelada", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("data_cancelamento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("xml_raw", sa.LargeBinary, nullable=False),
        sa.Column("contract_id", sa.String(64), sa.ForeignKey("contracts.contract_id"), nullable=True),
        sa.Column("participacao_id", sa.Integer, sa.ForeignKey("participacoes.id"), nullable=True),
        sa.Column("pagamento_id", sa.Integer, sa.ForeignKey("participacao_pagamentos.id"), nullable=True),
        sa.Column("status_matching", sa.String(20), nullable=False),
        sa.Column("motivo", sa.Text, nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("cnpj_prestador", "numero", "serie", name="uq_nfse_chave"),
    )
    op.create_index("idx_nfse_status", "nfse_recebidas", ["status_matching"])
    op.create_index("idx_nfse_tomador", "nfse_recebidas", ["tomador_doc", "competencia"])
    op.create_index("idx_nfse_contract", "nfse_recebidas", ["contract_id"])

    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cnpj_prestador", sa.String(14), nullable=False),
        sa.Column("origem", sa.String(20), nullable=False),
        sa.Column("disparado_por", sa.String(255), nullable=True),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("periodo_inicio", sa.Date, nullable=False),
        sa.Column("periodo_fim", sa.Date, nullable=False),
        sa.Column("total_nfs", sa.Integer, nullable=False, server_default="0"),
        sa.Column("auto_vinculadas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pendentes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sem_match", sa.Integer, nullable=False, server_default="0"),
        sa.Column("erros", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("motivo_falha", sa.Text, nullable=True),
        sa.Column("screenshot_url", sa.Text, nullable=True),
    )

    op.create_table(
        "nfse_audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("nfse_id", sa.Integer, sa.ForeignKey("nfse_recebidas.id"), nullable=True),
        sa.Column("credencial_id", sa.Integer, sa.ForeignKey("credencial_pbh.id"), nullable=True),
        sa.Column("acao", sa.String(50), nullable=False),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("payload_before", sa.JSON, nullable=True),
        sa.Column("payload_after", sa.JSON, nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("nfse_audit_log")
    op.drop_table("sync_jobs")
    op.drop_index("idx_nfse_contract", table_name="nfse_recebidas")
    op.drop_index("idx_nfse_tomador", table_name="nfse_recebidas")
    op.drop_index("idx_nfse_status", table_name="nfse_recebidas")
    op.drop_table("nfse_recebidas")
    op.drop_table("credencial_pbh")
