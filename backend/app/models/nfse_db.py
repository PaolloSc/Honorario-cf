"""SQLAlchemy models para NFS-e (espelha migration 0001)."""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.database import Base


class CredencialPbhDB(Base):
    __tablename__ = "credencial_pbh"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj_prestador = Column(String(14), nullable=False, unique=True)
    login_enc = Column(LargeBinary, nullable=False)
    senha_enc = Column(LargeBinary, nullable=False)
    nonce_login = Column(LargeBinary, nullable=False)
    nonce_senha = Column(LargeBinary, nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    motivo_inativacao = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    criado_por = Column(String(255), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), nullable=True)


class NFSeRecebidaDB(Base):
    __tablename__ = "nfse_recebidas"
    __table_args__ = (
        UniqueConstraint("cnpj_prestador", "numero", "serie", name="uq_nfse_chave"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj_prestador = Column(String(14), nullable=False)
    numero = Column(String(40), nullable=False)
    serie = Column(String(10), nullable=True)
    codigo_verificacao = Column(String(40), nullable=True)
    competencia = Column(Date, nullable=False)
    data_emissao = Column(Date, nullable=False)
    tomador_doc = Column(String(14), nullable=False)
    tomador_nome = Column(Text, nullable=True)
    valor_servicos = Column(Numeric(12, 2), nullable=False)
    iss_retido = Column(Numeric(12, 2), nullable=False, default=0)
    irrf = Column(Numeric(12, 2), nullable=False, default=0)
    pis = Column(Numeric(12, 2), nullable=False, default=0)
    cofins = Column(Numeric(12, 2), nullable=False, default=0)
    csll = Column(Numeric(12, 2), nullable=False, default=0)
    valor_liquido = Column(Numeric(12, 2), nullable=False)
    discriminacao = Column(Text, nullable=True)
    cancelada = Column(Boolean, nullable=False, default=False)
    data_cancelamento = Column(DateTime(timezone=True), nullable=True)
    xml_raw = Column(LargeBinary, nullable=False)
    contract_id = Column(String(64), ForeignKey("contracts.contract_id"), nullable=True)
    participacao_id = Column(Integer, ForeignKey("participacoes.id"), nullable=True)
    pagamento_id = Column(Integer, ForeignKey("participacao_pagamentos.id"), nullable=True)
    status_matching = Column(String(20), nullable=False)
    motivo = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), nullable=True)


class SyncJobDB(Base):
    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj_prestador = Column(String(14), nullable=False)
    origem = Column(String(20), nullable=False)
    disparado_por = Column(String(255), nullable=True)
    iniciado_em = Column(DateTime(timezone=True), nullable=False)
    finalizado_em = Column(DateTime(timezone=True), nullable=True)
    periodo_inicio = Column(Date, nullable=False)
    periodo_fim = Column(Date, nullable=False)
    total_nfs = Column(Integer, nullable=False, default=0)
    auto_vinculadas = Column(Integer, nullable=False, default=0)
    pendentes = Column(Integer, nullable=False, default=0)
    sem_match = Column(Integer, nullable=False, default=0)
    erros = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False)
    motivo_falha = Column(Text, nullable=True)
    screenshot_url = Column(Text, nullable=True)


class NFSeAuditLogDB(Base):
    __tablename__ = "nfse_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nfse_id = Column(Integer, ForeignKey("nfse_recebidas.id"), nullable=True)
    credencial_id = Column(Integer, ForeignKey("credencial_pbh.id"), nullable=True)
    acao = Column(String(50), nullable=False)
    user_email = Column(String(255), nullable=True)
    payload_before = Column(JSON, nullable=True)
    payload_after = Column(JSON, nullable=True)
    ts = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
