"""Emissao de NFS-e pelo Emissor Nacional: 8 tabelas

Revision ID: 0014_emissao_nfse
Revises: 0013_nfse_adn
Create Date: 2026-10-15

Producao nao tem alembic_version: aplicar o SQL idempotente de backend/sql/0014_emissao_nfse.sql a mao (ver PR).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_emissao_nfse"
down_revision = "0013_nfse_adn"
branch_labels = None
depends_on = None

TABELAS = [
    "nfse_emitida_eventos", "nfse_emitidas", "faturas", "contrato_faturamento",
    "tomadores", "servicos", "dps_sequence", "emissor_config",
]  # ordem de remocao: filhas antes das pais


def upgrade() -> None:
    op.create_table(
        "emissor_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("razao_social", sa.String(256), nullable=False),
        sa.Column("inscricao_municipal", sa.String(15), nullable=True),
        sa.Column("municipio_ibge", sa.String(7), nullable=False, server_default='3106200'),
        sa.Column("op_simp_nac", sa.String(1), nullable=False, server_default='1'),
        sa.Column("reg_ap_trib_sn", sa.String(1), nullable=True),
        sa.Column("reg_esp_trib", sa.String(1), nullable=False, server_default='0'),
        sa.Column("serie_dps", sa.String(5), nullable=False, server_default='900'),
        sa.Column("ambiente", sa.String(16), nullable=False, server_default='homologacao'),
        sa.Column("cert_pfx_enc", sa.LargeBinary(), nullable=True),
        sa.Column("cert_pfx_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("cert_senha_enc", sa.LargeBinary(), nullable=True),
        sa.Column("cert_senha_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("cert_titular", sa.String(256), nullable=True),
        sa.Column("cert_validade", sa.Date(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("atualizado_por", sa.String(255), nullable=True),
        sa.CheckConstraint("ambiente in ('homologacao','producao')", name="ck_emissor_ambiente"),
        sa.CheckConstraint('id = 1', name="ck_emissor_linha_unica"),
        sa.CheckConstraint("op_simp_nac in ('1','2','3')", name="ck_emissor_op_simp_nac"),
        sa.UniqueConstraint("cnpj"),
    )

    op.create_table(
        "dps_sequence",
        sa.Column("cnpj", sa.String(14), primary_key=True),
        sa.Column("serie", sa.String(5), primary_key=True),
        sa.Column("ambiente", sa.String(16), primary_key=True),
        sa.Column("ultimo_numero", sa.Integer(), nullable=False, server_default='0'),
    )

    op.create_table(
        "servicos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("descricao_padrao", sa.Text(), nullable=False),
        sa.Column("codigo_lc116", sa.String(10), nullable=True),
        sa.Column("c_trib_nac", sa.String(6), nullable=False),
        sa.Column("c_trib_mun", sa.String(3), nullable=True),
        sa.Column("nbs", sa.String(9), nullable=True),
        sa.Column("aliquota_iss", sa.Numeric(5, 2), nullable=True),
        sa.Column("iss_retido_padrao", sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column("incluir_ibscbs", sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column("c_ind_op", sa.String(6), nullable=True),
        sa.Column("cst_ibscbs", sa.String(3), nullable=True),
        sa.Column("c_class_trib", sa.String(6), nullable=True),
        sa.Column("tax_code_id", sa.Integer(), sa.ForeignKey("tax_codes.id"), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("criado_por", sa.String(255), nullable=False),
        sa.UniqueConstraint("nome"),
    )
    op.create_index("ix_servicos_tax_code_id", "servicos", ["tax_code_id"], unique=False)

    op.create_table(
        "tomadores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("documento", sa.String(14), nullable=False),
        sa.Column("nome", sa.String(256), nullable=False),
        sa.Column("emails", sa.JSON(), nullable=False),
        sa.Column("inscricao_municipal", sa.String(30), nullable=True),
        sa.Column("optante_simples", sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column("orgao_publico", sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column("cep", sa.String(8), nullable=True),
        sa.Column("logradouro", sa.String(256), nullable=True),
        sa.Column("numero", sa.String(20), nullable=True),
        sa.Column("complemento", sa.String(120), nullable=True),
        sa.Column("bairro", sa.String(120), nullable=True),
        sa.Column("municipio_ibge", sa.String(7), nullable=True),
        sa.Column("uf", sa.String(2), nullable=True),
        sa.Column("origem", sa.String(20), nullable=False, server_default='manual'),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("documento"),
    )

    op.create_table(
        "contrato_faturamento",
        sa.Column("contract_id", sa.String(64), sa.ForeignKey("contracts.contract_id"), primary_key=True),
        sa.Column("origem", sa.String(16), nullable=False, server_default='legalone'),
        sa.Column("tomador_id", sa.Integer(), sa.ForeignKey("tomadores.id"), nullable=True),
        sa.Column("servico_id", sa.Integer(), sa.ForeignKey("servicos.id"), nullable=True),
        sa.Column("gera_rascunho_mensal", sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("origem in ('legalone','honorario')", name="ck_cf_origem"),
    )

    op.create_table(
        "faturas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.String(64), sa.ForeignKey("contracts.contract_id"), nullable=False),
        sa.Column("tomador_id", sa.Integer(), sa.ForeignKey("tomadores.id"), nullable=False),
        sa.Column("servico_id", sa.Integer(), sa.ForeignKey("servicos.id"), nullable=False),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("valor_bruto", sa.Numeric(12, 2), nullable=False),
        sa.Column("vencimento", sa.Date(), nullable=True),
        sa.Column("parcela_num", sa.Integer(), nullable=False, server_default='1'),
        sa.Column("parcela_total", sa.Integer(), nullable=False, server_default='1'),
        sa.Column("origem", sa.String(16), nullable=False, server_default='manual'),
        sa.Column("status", sa.String(16), nullable=False, server_default='rascunho'),
        sa.Column("criada_por", sa.String(255), nullable=False),
        sa.Column("aprovada_por", sa.String(255), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("origem in ('manual','mensalidade','prolabore','exito','hora')", name="ck_fatura_origem"),
        sa.CheckConstraint("status in ('rascunho','aprovada','emitindo','emitida','cancelada')", name="ck_fatura_status"),
        sa.CheckConstraint('valor_bruto > 0', name="ck_fatura_valor"),
        sa.UniqueConstraint("contract_id", "competencia", "origem", "parcela_num", name="uq_fatura_geracao"),
    )
    op.create_index("ix_faturas_contract_id", "faturas", ["contract_id"], unique=False)
    op.create_index("ix_faturas_status", "faturas", ["status"], unique=False)
    op.create_index("ix_faturas_tomador_id", "faturas", ["tomador_id"], unique=False)

    op.create_table(
        "nfse_emitidas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fatura_id", sa.Integer(), sa.ForeignKey("faturas.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default='processando'),
        sa.Column("ambiente", sa.String(16), nullable=False),
        sa.Column("cnpj_prestador", sa.String(14), nullable=False),
        sa.Column("dps_serie", sa.String(5), nullable=False),
        sa.Column("dps_numero", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("chave_acesso", sa.String(60), nullable=True),
        sa.Column("numero_nfse", sa.String(40), nullable=True),
        sa.Column("valor_servicos", sa.Numeric(12, 2), nullable=False),
        sa.Column("iss", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("retencoes", sa.JSON(), nullable=False),
        sa.Column("tomador_snapshot", sa.JSON(), nullable=False),
        sa.Column("servico_snapshot", sa.JSON(), nullable=False),
        sa.Column("xml_dps", sa.LargeBinary(), nullable=True),
        sa.Column("xml_nfse", sa.LargeBinary(), nullable=True),
        sa.Column("erro_codigo", sa.String(20), nullable=True),
        sa.Column("erro_mensagem", sa.Text(), nullable=True),
        sa.Column("nfse_recebida_id", sa.Integer(), sa.ForeignKey("nfse_recebidas.id"), nullable=True),
        sa.Column("emitida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_cancelamento", sa.Text(), nullable=True),
        sa.Column("emitida_por", sa.String(255), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('processando','autorizada','rejeitada','cancelada')", name="ck_nfse_emitida_status"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("cnpj_prestador", "ambiente", "dps_serie", "dps_numero", name="uq_nfse_emitida_dps"),
    )
    op.create_index("ix_nfse_emitidas_fatura_id", "nfse_emitidas", ["fatura_id"], unique=False)
    op.create_index("ix_nfse_emitidas_status", "nfse_emitidas", ["status"], unique=False)
    op.create_index("uq_nfse_emitida_viva", "nfse_emitidas", ["fatura_id"], unique=True, postgresql_where=sa.text("status in ('processando','autorizada')"), sqlite_where=sa.text("status in ('processando','autorizada')"))

    op.create_table(
        "nfse_emitida_eventos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nfse_emitida_id", sa.Integer(), sa.ForeignKey("nfse_emitidas.id"), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_nfse_emitida_eventos_nfse_emitida_id", "nfse_emitida_eventos", ["nfse_emitida_id"], unique=False)


def downgrade() -> None:
    for t in TABELAS:
        op.drop_table(t)
