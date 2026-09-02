from __future__ import annotations

import json as _json
import os
import re as _re
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

# Support PostgreSQL (via DATABASE_URL env var, e.g. on Render) or fallback to local SQLite.
_default_sqlite = f"sqlite:///{Path(__file__).resolve().parent.parent / 'honorarios.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _default_sqlite)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Configure pool size for PostgreSQL to avoid cold-start delays
pool_kwargs: dict = {"pool_pre_ping": True}
if not DATABASE_URL.startswith("sqlite"):
    pool_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 10,
        "pool_recycle": 1800,
    })

engine = create_engine(DATABASE_URL, connect_args=connect_args, **pool_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# SQLite-specific pragmas (no-op when using PostgreSQL)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Users ─────────────────────────────────────────────────────────

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    azure_id = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    name = Column(String(256), nullable=False, default="")
    role = Column(String(32), nullable=False, default="advogado")  # advogado | admin
    created_at = Column(DateTime, nullable=False, default=utcnow)


# ── Testemunhas (roster) ──────────────────────────────────────────

class TestemunhaDB(Base):
    """Cadastro de testemunhas recorrentes do escritorio (roster)."""

    __tablename__ = "testemunhas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(256), nullable=False)
    email = Column(String(256), nullable=False, index=True)
    ativo = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(256), nullable=True)  # user email
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


# ── Colaboradores (roster interno: advogados/sócios/etc.) ─────────

PAPEIS_VALIDOS = (
    "socio",
    "advogado",
    "estagiario",
    "recepcionista",
    "financeiro",
    "dev",
)
# Papéis elegíveis a participação (advogados/sócios) — usados nos
# campos "Para quem", responsáveis etc. do wizard.
PAPEIS_PARTICIPAVEIS = ("socio", "advogado")


class ColaboradorDB(Base):
    """Cadastro interno de colaboradores do escritório (roster).

    Fonte da lista suspensa de advogados/sócios no wizard. Diferente de
    ``UserDB`` (contas de login Azure): aqui ficam todas as pessoas do
    escritório, tenham logado ou não.
    """

    __tablename__ = "colaboradores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(256), nullable=False)
    email = Column(String(256), nullable=True)
    papel = Column(String(32), nullable=False, default="advogado")  # ver PAPEIS_VALIDOS
    ativo = Column(Boolean, nullable=False, default=True)
    ordem = Column(Integer, nullable=False, default=0)
    created_by = Column(String(256), nullable=True)  # user email
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    @property
    def participavel(self) -> bool:
        return self.papel in PAPEIS_PARTICIPAVEIS


LEGALONE_TIPOS_VALIDOS = ("categoria_cliente", "etiqueta", "lista_transmissao")


class LegalOneOpcaoDB(Base):
    """Opções das tabelas do Legal One usadas na ficha do financeiro.

    Uma tabela para as três listas (categoria de cliente, etiqueta, lista de
    transmissão) porque têm forma idêntica. Mantidas pelo admin em /admin/legalone.
    """

    __tablename__ = "legalone_opcoes"
    __table_args__ = (
        UniqueConstraint("tipo", "valor", name="uq_legalone_opcao"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(String(32), nullable=False)  # ver LEGALONE_TIPOS_VALIDOS
    valor = Column(String(256), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


# ── Contracts ─────────────────────────────────────────────────────

class ContractDB(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="rascunho")
    client_name = Column(String(256), nullable=False, default="")
    client_email = Column(String(256), nullable=False, default="")
    tipo_contrato = Column(String(32), nullable=False, default="honorarios", server_default="honorarios")
    current_version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(256), nullable=True)  # user email
    updated_by = Column(String(256), nullable=True)  # user email
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    cliente_docs = Column(Text, nullable=False, default="[]")

    versions = relationship(
        "ContractVersionDB", back_populates="contract", order_by="ContractVersionDB.version_number"
    )
    audit_logs = relationship(
        "AuditLogDB", back_populates="contract", order_by="AuditLogDB.created_at.desc()"
    )


def derive_cliente_docs(form_data: dict) -> list[str]:
    """Extrai CPF/CNPJ normalizados dos contratantes."""
    docs: set[str] = set()
    for contratante in form_data.get("contratantes", []) or []:
        raw = contratante.get("cnpj") or contratante.get("cpf") or ""
        doc = _re.sub(r"\D", "", raw)
        if doc:
            docs.add(doc)
    return sorted(docs)


def serialize_cliente_docs(form_data: dict) -> str:
    return _json.dumps(derive_cliente_docs(form_data))


class ContractVersionDB(Base):
    __tablename__ = "contract_versions"
    __table_args__ = (
        UniqueConstraint("contract_id", "version_number", name="uq_contract_version"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(64), ForeignKey("contracts.contract_id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    form_data_json = Column(Text, nullable=False)
    file_path = Column(String(512), nullable=True)
    docuseal_submission_id = Column(String(128), nullable=True)
    created_by = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    contract = relationship("ContractDB", back_populates="versions")


class AuditLogDB(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(64), ForeignKey("contracts.contract_id"), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    detail = Column(Text, nullable=True)
    version_number = Column(Integer, nullable=True)
    user_email = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    contract = relationship("ContractDB", back_populates="audit_logs")


# ── Participações (Setor Financeiro) ─────────────────────────────

class ParticipacaoDB(Base):
    """Participação interna de advogado em honorários contratuais.

    Regras (vigência a partir de 2024-08-01, sem retroatividade):
    - Aplica-se apenas a honorários contratuais (sucumbenciais excluídos).
    - Captação até 20%, Performance até 20%, combo até 40%.
    - Limite temporal por tipo: hora=3a, partido=2a, mensalidade=2a, êxito/prolabore=sem limite.
    - Vínculo ativo (contratual ou societário) é pré-condição de pagamento.
    """

    __tablename__ = "participacoes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(64), ForeignKey("contracts.contract_id"), nullable=False, index=True)
    beneficiario_email = Column(String(256), nullable=False, index=True)
    beneficiario_nome = Column(String(256), nullable=False, default="")
    tipo_honorario = Column(String(32), nullable=False)  # hora|partido|mensalidade|exito|prolabore|misto
    percentual_captacao = Column(Float, nullable=False, default=0.0)
    percentual_performance = Column(Float, nullable=False, default=0.0)
    motivo_captacao = Column(Text, nullable=True)
    motivo_performance = Column(Text, nullable=True)
    natureza = Column(String(32), nullable=False, default="contratual")  # contratual|societario
    cliente_cpf_cnpj = Column(String(32), nullable=True, index=True)
    data_inicio = Column(Date, nullable=False)  # >= 2024-08-01
    vinculo_ativo = Column(Boolean, nullable=False, default=True)
    data_fim_vinculo = Column(Date, nullable=True)
    aprovado_por = Column(String(256), nullable=True)
    aprovada = Column(Boolean, nullable=False, default=False)  # False=rascunho do wizard; True=validada pelo financeiro
    observacoes = Column(Text, nullable=True)
    created_by = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    pagamentos = relationship(
        "ParticipacaoPagamentoDB",
        back_populates="participacao",
        order_by="ParticipacaoPagamentoDB.data_recebimento",
    )


class ParticipacaoPagamentoDB(Base):
    """Recebimento de honorário (valor líquido) a partir do qual se calcula a participação."""

    __tablename__ = "participacao_pagamentos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    participacao_id = Column(Integer, ForeignKey("participacoes.id"), nullable=False, index=True)
    data_recebimento = Column(Date, nullable=False)
    valor_liquido_recebido = Column(Float, nullable=False)
    valor_participacao = Column(Float, nullable=False)
    dentro_limite_temporal = Column(Boolean, nullable=False, default=True)
    observacoes = Column(Text, nullable=True)
    registrado_por = Column(String(256), nullable=True)
    status = Column(String(32), nullable=False, default="aguardando_pagamento", index=True)
    parcela_num = Column(Integer, nullable=False, default=1)
    parcela_total = Column(Integer, nullable=False, default=1)
    nf_referencia = Column(String(64), nullable=True, index=True)
    tax_code_id = Column(Integer, ForeignKey("tax_codes.id"), nullable=True, index=True)
    valor_bruto = Column(Float, nullable=True)
    imposto_total = Column(Float, nullable=False, default=0, server_default="0")
    tipo_cobranca = Column(String(32), nullable=True)
    natureza_pagamento = Column(String(32), nullable=True, index=True)
    tipo_documento = Column(String(32), nullable=False, default="nf", server_default="nf")
    created_at = Column(DateTime, nullable=False, default=utcnow)

    participacao = relationship("ParticipacaoDB", back_populates="pagamentos")


class TaxCodeDB(Base):
    """Código fiscal (master data SAP-like). Alíquotas agregadas para retenções."""

    __tablename__ = "tax_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(32), unique=True, nullable=False, index=True)
    descricao = Column(String(256), nullable=False)
    aliquota_total = Column(Numeric(5, 4), nullable=False)
    aliquota_iss = Column(Numeric(5, 4), nullable=False, default=0)
    aliquota_pis = Column(Numeric(5, 4), nullable=False, default=0)
    aliquota_cofins = Column(Numeric(5, 4), nullable=False, default=0)
    aliquota_irrf = Column(Numeric(5, 4), nullable=False, default=0)
    aliquota_csll = Column(Numeric(5, 4), nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=utcnow)
    criado_por = Column(String(256), nullable=False)


def init_db():
    # TODO: For production, replace create_all() with Alembic migrations to handle
    # schema changes safely (alembic init / alembic revision --autogenerate / alembic upgrade head).
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
