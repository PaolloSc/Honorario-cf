# NFS-e PBH no Financeiro — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ao Honorario-cf a capacidade do setor financeiro puxar NFS-e da Prefeitura de Belo Horizonte (BHISS Digital), parsear, casar com contratos existentes, gerar pagamentos na Participação e produzir relatório comparativo.

**Architecture:** Worker headless Playwright rodando em GitHub Actions consulta o portal BHISS Digital com credenciais armazenadas criptografadas (AES-GCM) no banco; XMLs são parseados e enviados a endpoints internos do backend FastAPI (Render). Matcher casa NF↔contrato por documento do tomador + competência (fallback `#contract_id` na discriminação) e dispara pagamento via service de Participação existente.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Pydantic v2, cryptography (AES-GCM), defusedxml, lxml, Playwright (worker), pytest. Frontend Next.js 15 + TypeScript + Tailwind. CI/CD GitHub Actions + Render + Vercel.

**Spec:** `docs/superpowers/specs/2026-05-20-nfse-bh-financeiro-design.md`

**Conventions used:**
- Caminhos de arquivos relativos à raiz do submodule `Honorario-cf/` salvo nota em contrário.
- Banco principal: `participacao_pagamentos` (não `pagamentos`); `contracts.contract_id` (VARCHAR(64)) é a chave externa lógica (não `contracts.id` numérico).
- `cliente_doc` = somente dígitos (CPF 11 ou CNPJ 14).
- Datas/competência em `America/Sao_Paulo`; timestamps em UTC (TZ-aware).

---

## Phase 1 — Foundation

### Task 1: Atualizar `requirements.txt`

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Adicionar novas dependências ao requirements.txt**

Adicionar (ou garantir presença) ao final do arquivo:

```
alembic==1.13.2
cryptography==43.0.1
defusedxml==0.7.1
lxml==5.3.0
python-dateutil==2.9.0
tzdata==2024.2
```

`slowapi` já presente (visto em `app/main.py`). Não duplicar.

- [ ] **Step 2: Instalar e verificar**

```powershell
cd backend
.venv\Scripts\activate
pip install -r requirements.txt
python -c "import alembic, cryptography, defusedxml, lxml, dateutil, tzdata; print('ok')"
```

Esperado: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(nfse): add deps para NFS-e (alembic, cryptography, defusedxml, lxml, dateutil)"
```

---

### Task 2: Estender `app/config.py` com env NFS-e

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Adicionar campos ao `Settings`**

Localizar bloco de campos em `app/config.py` (após `dev_mode: bool = False`) e adicionar antes de `model_config`:

```python
    # NFS-e BH (financeiro)
    nfse_enabled: bool = False
    nfse_kek: str = ""                       # base64 32 bytes (AES-GCM)
    nfse_worker_token: str = ""              # bearer p/ worker GH Actions
    nfse_backfill_days: int = 90
    nfse_gh_actions_cidrs: str = ""          # CSV, opcional (allowlist)
```

E ao final de `validate_critical()`:

```python
        if self.nfse_enabled:
            if not self.nfse_kek:
                missing.append("NFSE_KEK")
            if not self.nfse_worker_token:
                missing.append("NFSE_WORKER_TOKEN")
```

- [ ] **Step 2: Smoke local**

```powershell
cd backend
.venv\Scripts\activate
python -c "from app.config import settings; print(settings.nfse_enabled, settings.nfse_backfill_days)"
```

Esperado: `False 90`.

- [ ] **Step 3: Atualizar `.env.example`**

Adicionar ao final de `backend/.env.example`:

```
# NFS-e BH
NFSE_ENABLED=false
NFSE_KEK=                            # base64(32 bytes) — gerar com: python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
NFSE_WORKER_TOKEN=                   # 48+ chars aleatórios
NFSE_BACKFILL_DAYS=90
NFSE_GH_ACTIONS_CIDRS=               # opcional, CSV
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/.env.example
git commit -m "feat(nfse): config envs (NFSE_ENABLED, NFSE_KEK, NFSE_WORKER_TOKEN, NFSE_BACKFILL_DAYS)"
```

---

### Task 3: Service `crypto.py` (AES-GCM) com TDD

**Files:**
- Create: `backend/app/services/crypto.py`
- Test: `backend/tests/test_crypto.py`

- [ ] **Step 1: Escrever testes que falham**

Criar `backend/tests/__init__.py` se não existir (arquivo vazio).

Criar `backend/tests/test_crypto.py`:

```python
import base64
import os

import pytest

from app.services.crypto import CryptoBox, InvalidCipherError


@pytest.fixture
def kek_b64() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def test_roundtrip(kek_b64):
    box = CryptoBox(kek_b64)
    plaintext = "minha-senha-pbh-123!@#"
    blob = box.encrypt(plaintext)
    assert box.decrypt(blob) == plaintext


def test_distinct_nonces_per_write(kek_b64):
    box = CryptoBox(kek_b64)
    a = box.encrypt("x")
    b = box.encrypt("x")
    assert a.nonce != b.nonce
    assert a.ciphertext != b.ciphertext


def test_wrong_key_fails(kek_b64):
    box1 = CryptoBox(kek_b64)
    blob = box1.encrypt("hello")
    other = base64.b64encode(os.urandom(32)).decode()
    box2 = CryptoBox(other)
    with pytest.raises(InvalidCipherError):
        box2.decrypt(blob)


def test_tampered_ciphertext_fails(kek_b64):
    box = CryptoBox(kek_b64)
    blob = box.encrypt("hello")
    tampered = type(blob)(nonce=blob.nonce, ciphertext=blob.ciphertext[:-1] + b"\x00")
    with pytest.raises(InvalidCipherError):
        box.decrypt(tampered)


def test_invalid_kek_length():
    bad = base64.b64encode(os.urandom(16)).decode()
    with pytest.raises(ValueError):
        CryptoBox(bad)
```

- [ ] **Step 2: Rodar e verificar que falha**

```powershell
cd backend
pytest tests/test_crypto.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.services.crypto'`.

- [ ] **Step 3: Implementar `app/services/crypto.py`**

```python
"""AES-GCM envelope encryption para credenciais PBH em repouso.

KEK (Key Encryption Key) de 32 bytes vem em base64 via env NFSE_KEK.
Cada write gera nonce de 96 bits único.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class InvalidCipherError(Exception):
    """Raised when decryption fails (wrong key, tampered ciphertext, etc.)."""


@dataclass(frozen=True)
class EncryptedBlob:
    nonce: bytes      # 12 bytes
    ciphertext: bytes # includes 16-byte auth tag at the end (AESGCM convention)


class CryptoBox:
    NONCE_LEN = 12

    def __init__(self, kek_b64: str) -> None:
        key = base64.b64decode(kek_b64)
        if len(key) != 32:
            raise ValueError(f"KEK deve ter 32 bytes, recebido {len(key)}")
        self._aead = AESGCM(key)

    def encrypt(self, plaintext: str) -> EncryptedBlob:
        nonce = os.urandom(self.NONCE_LEN)
        ct = self._aead.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
        return EncryptedBlob(nonce=nonce, ciphertext=ct)

    def decrypt(self, blob: EncryptedBlob) -> str:
        try:
            pt = self._aead.decrypt(blob.nonce, blob.ciphertext, associated_data=None)
        except InvalidTag as e:
            raise InvalidCipherError("falha ao decifrar (tag inválida)") from e
        return pt.decode("utf-8")
```

- [ ] **Step 4: Rodar testes — devem passar**

```powershell
pytest tests/test_crypto.py -v
```

Esperado: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/crypto.py backend/tests/test_crypto.py backend/tests/__init__.py
git commit -m "feat(nfse): CryptoBox AES-GCM com testes de roundtrip, nonces, tampering"
```

---

### Task 4: Setup Alembic + migration NFS-e tables

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/__init__.py`
- Create: `backend/alembic/versions/0001_nfse_tables.py`
- Modify: `backend/app/database.py` (remove `init_db()` chamada em `main.py` em Task 17; aqui só adicionamos suporte)

- [x] **Step 1: Inicializar Alembic**

```powershell
cd backend
.venv\Scripts\activate
alembic init alembic
```

Isso cria `alembic.ini` e diretório `alembic/`.

- [x] **Step 2: Configurar `alembic.ini`**

Editar `backend/alembic.ini`, localizar `sqlalchemy.url =` e deixar **vazio** (será lido via env):

```
sqlalchemy.url =
```

- [x] **Step 3: Configurar `alembic/env.py`**

Substituir conteúdo de `backend/alembic/env.py` por:

```python
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Garantir que `app.*` é importável quando alembic roda da pasta backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base  # noqa: E402

# Carrega todos os models para metadata
import app.database  # noqa: F401,E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv("DATABASE_URL")
if not database_url:
    backend_dir = Path(__file__).resolve().parent.parent
    database_url = f"sqlite:///{backend_dir / 'honorarios.db'}"
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [x] **Step 4: Criar migração `0001_nfse_tables.py`**

Criar `backend/alembic/versions/__init__.py` (vazio) se necessário.

Criar `backend/alembic/versions/0001_nfse_tables.py`:

```python
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
```

- [x] **Step 5: Stamp DB existente como base e aplicar migração**

```powershell
cd backend
.venv\Scripts\activate
# Marcar estado atual como pré-migração (não rodar nada pre-existente)
alembic stamp head
# Voltar para nenhum head, depois aplicar 0001
alembic stamp base
alembic upgrade head
```

Esperado: tabelas criadas. Verificar:

```powershell
python -c "from app.database import engine; from sqlalchemy import inspect; print(sorted(inspect(engine).get_table_names()))"
```

Esperado inclui: `credencial_pbh`, `nfse_audit_log`, `nfse_recebidas`, `sync_jobs`.

- [x] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic
git commit -m "feat(nfse): alembic setup + migration 0001 (credencial_pbh, nfse_recebidas, sync_jobs, audit_log)"
```

---

### Task 5: Migration `contracts.cliente_docs` + backfill

**Files:**
- Create: `backend/alembic/versions/0002_contracts_cliente_docs.py`
- Modify: `backend/app/database.py` (adicionar coluna no `ContractDB`)
- Modify: `backend/app/routers/contract.py` (atualizar `cliente_docs` ao salvar)

- [x] **Step 1: Adicionar coluna em `ContractDB`**

Em `backend/app/database.py`, dentro da classe `ContractDB`, após `updated_at`:

```python
    cliente_docs = Column(Text, nullable=False, default="[]")  # JSON array de CPF/CNPJ normalizado
```

(Usamos `Text` JSON serializado p/ compatibilidade SQLite. Postgres aceitaria `JSONB`, mas mantemos consistência.)

- [x] **Step 2: Criar migration `0002_contracts_cliente_docs.py`**

```python
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

    # Backfill: ler form_data_json da última version de cada contrato e extrair docs
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
            for c in data.get("contratantes", []) or []:
                doc = _only_digits(c.get("cnpj") or c.get("cpf"))
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
```

- [x] **Step 3: Helper p/ derivar `cliente_docs` ao salvar contrato**

Em `backend/app/database.py`, após classe `ContractDB`, adicionar função utilitária:

```python
import json as _json
import re as _re


def derive_cliente_docs(form_data: dict) -> list[str]:
    """Extrai CPF/CNPJ normalizados (só dígitos) dos contratantes."""
    docs: set[str] = set()
    for c in form_data.get("contratantes", []) or []:
        raw = c.get("cnpj") or c.get("cpf") or ""
        d = _re.sub(r"\D", "", raw)
        if d:
            docs.add(d)
    return sorted(docs)


def serialize_cliente_docs(form_data: dict) -> str:
    return _json.dumps(derive_cliente_docs(form_data))
```

- [x] **Step 4: Chamar derive em `routers/contract.py`**

Localizar em `backend/app/routers/contract.py` os pontos que criam ou atualizam `ContractDB` (procurar por `ContractDB(` e `current_version`). Em cada save/update, antes do commit, definir `contract.cliente_docs = serialize_cliente_docs(form_data_dict)`.

Como o arquivo é grande e não conhecemos o cursor exato, adicionar import no topo:

```python
from app.database import derive_cliente_docs, serialize_cliente_docs
```

E em cada bloco que faz `contract.current_version = ...` adicionar logo abaixo:

```python
contract.cliente_docs = serialize_cliente_docs(form_dict)
```

onde `form_dict` é o dict do `ContratoRequest.model_dump()` ou equivalente já presente no contexto.

- [x] **Step 5: Aplicar migração**

```powershell
cd backend
alembic upgrade head
python -c "from app.database import SessionLocal; from sqlalchemy import text; s=SessionLocal(); print(s.execute(text('SELECT contract_id, cliente_docs FROM contracts LIMIT 5')).fetchall())"
```

Esperado: linhas com `cliente_docs` populadas (JSON arrays) ou `[]` se contrato sem contratante.

- [x] **Step 6: Commit**

```bash
git add backend/alembic/versions/0002_contracts_cliente_docs.py backend/app/database.py backend/app/routers/contract.py
git commit -m "feat(nfse): coluna contracts.cliente_docs + backfill + derive on save"
```

---

## Phase 2 — Models, Parser, Matcher

### Task 6: SQLAlchemy models NFS-e (Credencial, NFSeRecebida, SyncJob, AuditLog)

**Files:**
- Create: `backend/app/models/nfse_db.py`

- [x] **Step 1: Criar `app/models/nfse_db.py`**

```python
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
```

- [x] **Step 2: Smoke import**

```powershell
cd backend
python -c "from app.models.nfse_db import CredencialPbhDB, NFSeRecebidaDB, SyncJobDB, NFSeAuditLogDB; print('ok')"
```

Esperado: `ok`.

- [x] **Step 3: Commit**

```bash
git add backend/app/models/nfse_db.py
git commit -m "feat(nfse): SQLAlchemy models (Credencial, NFSeRecebida, SyncJob, AuditLog)"
```

---

### Task 7: Pydantic schema `NFSeData`

**Files:**
- Create: `backend/app/models/nfse.py`

- [x] **Step 1: Criar `app/models/nfse.py`**

```python
"""Schemas Pydantic para NFS-e."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class NFSeData(BaseModel):
    """Representação canônica de uma NFS-e após parse XML."""

    cnpj_prestador: str = Field(..., min_length=14, max_length=14)
    numero: str
    serie: Optional[str] = None
    codigo_verificacao: Optional[str] = None
    competencia: date
    data_emissao: date
    tomador_doc: str   # CPF (11) ou CNPJ (14), só dígitos
    tomador_nome: Optional[str] = None
    valor_servicos: Decimal
    iss_retido: Decimal = Decimal("0")
    irrf: Decimal = Decimal("0")
    pis: Decimal = Decimal("0")
    cofins: Decimal = Decimal("0")
    csll: Decimal = Decimal("0")
    discriminacao: Optional[str] = None
    cancelada: bool = False
    data_cancelamento: Optional[datetime] = None
    xml_raw: bytes

    @computed_field
    @property
    def valor_liquido(self) -> Decimal:
        return (
            self.valor_servicos
            - self.iss_retido
            - self.irrf
            - self.pis
            - self.cofins
            - self.csll
        )


class CredencialPbhCreate(BaseModel):
    cnpj_prestador: str = Field(..., min_length=14, max_length=14)
    login: str
    senha: str


class CredencialPbhOut(BaseModel):
    id: int
    cnpj_prestador: str
    ativo: bool
    criado_em: datetime
    criado_por: str
    motivo_inativacao: Optional[str] = None


class NFSeOut(BaseModel):
    id: int
    cnpj_prestador: str
    numero: str
    serie: Optional[str]
    competencia: date
    data_emissao: date
    tomador_doc: str
    tomador_nome: Optional[str]
    valor_servicos: Decimal
    valor_liquido: Decimal
    cancelada: bool
    status_matching: str
    contract_id: Optional[str]
    participacao_id: Optional[int]
    pagamento_id: Optional[int]
    motivo: Optional[str]

    model_config = {"from_attributes": True}


class VincularRequest(BaseModel):
    contract_id: str
    motivo: Optional[str] = None


class IngestRequest(BaseModel):
    cnpj_prestador: str
    periodo_inicio: date
    periodo_fim: date
    origem: str = "cron"  # cron | manual | workflow_dispatch
    disparado_por: Optional[str] = None
    xmls_b64: list[str]   # base64 do XML cada NFS-e


class SyncJobOut(BaseModel):
    id: int
    cnpj_prestador: str
    origem: str
    iniciado_em: datetime
    finalizado_em: Optional[datetime]
    periodo_inicio: date
    periodo_fim: date
    total_nfs: int
    auto_vinculadas: int
    pendentes: int
    sem_match: int
    erros: int
    status: str
    motivo_falha: Optional[str]

    model_config = {"from_attributes": True}
```

- [x] **Step 2: Smoke**

```powershell
cd backend
python -c "from app.models.nfse import NFSeData; from decimal import Decimal; from datetime import date; n=NFSeData(cnpj_prestador='12345678000199', numero='1', competencia=date(2026,5,1), data_emissao=date(2026,5,2), tomador_doc='98765432000100', valor_servicos=Decimal('1000'), iss_retido=Decimal('30'), xml_raw=b'x'); print(n.valor_liquido)"
```

Esperado: `970`.

- [x] **Step 3: Commit**

```bash
git add backend/app/models/nfse.py
git commit -m "feat(nfse): Pydantic schemas (NFSeData, Credencial, Vincular, Ingest, SyncJob)"
```

---

### Task 8: Parser de XML NFS-e (TDD)

**Files:**
- Create: `backend/tests/fixtures/nfse/abrasf_minimo.xml`
- Create: `backend/tests/fixtures/nfse/abrasf_pf_tomador.xml`
- Create: `backend/tests/fixtures/nfse/abrasf_cancelada.xml`
- Create: `backend/tests/fixtures/nfse/abrasf_com_retencoes.xml`
- Create: `backend/tests/fixtures/nfse/abrasf_malformado.xml`
- Create: `backend/tests/fixtures/nfse/xxe_attack.xml`
- Create: `backend/tests/test_nfse_parser.py`
- Create: `backend/app/services/nfse_parser.py`

- [x] **Step 1: Criar fixtures XML**

Criar `backend/tests/fixtures/nfse/abrasf_minimo.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd">
  <Nfse>
    <InfNfse Id="nfse-1">
      <Numero>1000</Numero>
      <CodigoVerificacao>ABC123</CodigoVerificacao>
      <DataEmissao>2026-05-10T10:00:00</DataEmissao>
      <Competencia>2026-05-01</Competencia>
      <Servico>
        <Valores>
          <ValorServicos>1500.00</ValorServicos>
          <ValorIss>0</ValorIss>
        </Valores>
        <Discriminacao>Honorarios advocaticios maio/2026</Discriminacao>
      </Servico>
      <PrestadorServico>
        <IdentificacaoPrestador>
          <Cnpj>12345678000199</Cnpj>
        </IdentificacaoPrestador>
        <RazaoSocial>Escritorio C&amp;F</RazaoSocial>
      </PrestadorServico>
      <TomadorServico>
        <IdentificacaoTomador>
          <CpfCnpj>
            <Cnpj>98765432000100</Cnpj>
          </CpfCnpj>
        </IdentificacaoTomador>
        <RazaoSocial>Cliente Exemplo LTDA</RazaoSocial>
      </TomadorServico>
    </InfNfse>
  </Nfse>
</CompNfse>
```

Criar `backend/tests/fixtures/nfse/abrasf_pf_tomador.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd">
  <Nfse>
    <InfNfse Id="nfse-2">
      <Numero>1001</Numero>
      <DataEmissao>2026-05-12T09:00:00</DataEmissao>
      <Competencia>2026-05-01</Competencia>
      <Servico>
        <Valores>
          <ValorServicos>2000.00</ValorServicos>
        </Valores>
        <Discriminacao>Consultoria #abc12345 maio</Discriminacao>
      </Servico>
      <PrestadorServico>
        <IdentificacaoPrestador>
          <Cnpj>12345678000199</Cnpj>
        </IdentificacaoPrestador>
      </PrestadorServico>
      <TomadorServico>
        <IdentificacaoTomador>
          <CpfCnpj>
            <Cpf>12345678901</Cpf>
          </CpfCnpj>
        </IdentificacaoTomador>
        <RazaoSocial>Joao Silva</RazaoSocial>
      </TomadorServico>
    </InfNfse>
  </Nfse>
</CompNfse>
```

Criar `backend/tests/fixtures/nfse/abrasf_cancelada.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd">
  <Nfse>
    <InfNfse Id="nfse-3">
      <Numero>1002</Numero>
      <DataEmissao>2026-05-13T11:00:00</DataEmissao>
      <Competencia>2026-05-01</Competencia>
      <Servico>
        <Valores><ValorServicos>500.00</ValorServicos></Valores>
        <Discriminacao>servicos</Discriminacao>
      </Servico>
      <PrestadorServico>
        <IdentificacaoPrestador><Cnpj>12345678000199</Cnpj></IdentificacaoPrestador>
      </PrestadorServico>
      <TomadorServico>
        <IdentificacaoTomador>
          <CpfCnpj><Cnpj>98765432000100</Cnpj></CpfCnpj>
        </IdentificacaoTomador>
      </TomadorServico>
    </InfNfse>
  </Nfse>
  <NfseCancelamento>
    <Confirmacao>
      <DataHora>2026-05-14T15:00:00</DataHora>
    </Confirmacao>
  </NfseCancelamento>
</CompNfse>
```

Criar `backend/tests/fixtures/nfse/abrasf_com_retencoes.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd">
  <Nfse>
    <InfNfse Id="nfse-4">
      <Numero>1003</Numero>
      <DataEmissao>2026-05-15T08:00:00</DataEmissao>
      <Competencia>2026-05-01</Competencia>
      <Servico>
        <Valores>
          <ValorServicos>10000.00</ValorServicos>
          <ValorIss>500.00</ValorIss>
          <IssRetido>1</IssRetido>
          <ValorPis>65.00</ValorPis>
          <ValorCofins>300.00</ValorCofins>
          <ValorIr>150.00</ValorIr>
          <ValorCsll>100.00</ValorCsll>
        </Valores>
        <Discriminacao>Honorarios consultoria</Discriminacao>
      </Servico>
      <PrestadorServico>
        <IdentificacaoPrestador><Cnpj>12345678000199</Cnpj></IdentificacaoPrestador>
      </PrestadorServico>
      <TomadorServico>
        <IdentificacaoTomador>
          <CpfCnpj><Cnpj>11222333000144</Cnpj></CpfCnpj>
        </IdentificacaoTomador>
      </TomadorServico>
    </InfNfse>
  </Nfse>
</CompNfse>
```

Criar `backend/tests/fixtures/nfse/abrasf_malformado.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CompNfse><Nfse><InfNfse><Numero>X
```

Criar `backend/tests/fixtures/nfse/xxe_attack.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ELEMENT foo ANY>
  <!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<CompNfse><Nfse><InfNfse><Numero>&xxe;</Numero></InfNfse></Nfse></CompNfse>
```

- [x] **Step 2: Escrever testes**

Criar `backend/tests/test_nfse_parser.py`:

```python
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.nfse_parser import NFSeParseError, parse_nfse_xml

FIXTURES = Path(__file__).parent / "fixtures" / "nfse"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parse_minimo_pj_tomador():
    nf = parse_nfse_xml(_load("abrasf_minimo.xml"))
    assert nf.cnpj_prestador == "12345678000199"
    assert nf.numero == "1000"
    assert nf.codigo_verificacao == "ABC123"
    assert nf.tomador_doc == "98765432000100"
    assert nf.tomador_nome == "Cliente Exemplo LTDA"
    assert nf.valor_servicos == Decimal("1500.00")
    assert nf.iss_retido == Decimal("0")
    assert nf.cancelada is False
    assert "maio/2026" in (nf.discriminacao or "")


def test_parse_pf_tomador():
    nf = parse_nfse_xml(_load("abrasf_pf_tomador.xml"))
    assert nf.tomador_doc == "12345678901"
    assert "abc12345" in (nf.discriminacao or "").lower()


def test_parse_cancelada():
    nf = parse_nfse_xml(_load("abrasf_cancelada.xml"))
    assert nf.cancelada is True
    assert nf.data_cancelamento is not None


def test_parse_com_retencoes_federais():
    nf = parse_nfse_xml(_load("abrasf_com_retencoes.xml"))
    assert nf.valor_servicos == Decimal("10000.00")
    assert nf.iss_retido == Decimal("500.00")
    assert nf.pis == Decimal("65.00")
    assert nf.cofins == Decimal("300.00")
    assert nf.irrf == Decimal("150.00")
    assert nf.csll == Decimal("100.00")
    assert nf.valor_liquido == Decimal("8885.00")


def test_parse_malformado_levanta():
    with pytest.raises(NFSeParseError):
        parse_nfse_xml(_load("abrasf_malformado.xml"))


def test_xxe_bloqueado():
    # defusedxml deve recusar DTD externo
    with pytest.raises(NFSeParseError):
        parse_nfse_xml(_load("xxe_attack.xml"))
```

- [x] **Step 3: Rodar e ver falha**

```powershell
cd backend
pytest tests/test_nfse_parser.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.services.nfse_parser'`.

- [x] **Step 4: Implementar parser**

Criar `backend/app/services/nfse_parser.py`:

```python
"""Parser de NFS-e ABRASF (variante BHISS). Usa defusedxml p/ mitigar XXE."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from defusedxml.ElementTree import ParseError, fromstring


class NFSeParseError(Exception):
    pass


_NS = {"a": "http://www.abrasf.org.br/nfse.xsd"}


def _digits(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\D", "", s)


def _txt(elem, path: str) -> str | None:
    """Tenta com e sem namespace. Retorna texto ou None."""
    if elem is None:
        return None
    # com namespace
    found = elem.find(path, _NS)
    if found is None:
        # sem namespace
        no_ns_path = re.sub(r"a:", "", path)
        found = elem.find(no_ns_path)
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _decimal(s: str | None) -> Decimal:
    if not s:
        return Decimal("0")
    return Decimal(s)


def parse_nfse_xml(xml: bytes) -> "NFSeData":
    from app.models.nfse import NFSeData

    try:
        root = fromstring(xml)
    except (ParseError, Exception) as e:
        # defusedxml levanta EntitiesForbidden p/ XXE; ParseError p/ malformado
        raise NFSeParseError(f"XML inválido: {e}") from e

    inf = root.find(".//a:InfNfse", _NS) or root.find(".//InfNfse")
    if inf is None:
        raise NFSeParseError("InfNfse não encontrado")

    numero = _txt(inf, "a:Numero")
    if not numero:
        raise NFSeParseError("Numero ausente")

    codigo_ver = _txt(inf, "a:CodigoVerificacao")

    competencia_str = _txt(inf, "a:Competencia")
    data_emissao_str = _txt(inf, "a:DataEmissao")
    if not competencia_str or not data_emissao_str:
        raise NFSeParseError("Competencia/DataEmissao ausente")

    competencia = date.fromisoformat(competencia_str[:10])
    data_emissao = date.fromisoformat(data_emissao_str[:10])

    # Servico/Valores
    valores = inf.find("a:Servico/a:Valores", _NS) or inf.find("Servico/Valores")
    if valores is None:
        raise NFSeParseError("Servico/Valores ausente")

    valor_servicos = _decimal(_txt(valores, "a:ValorServicos"))
    iss_retido_flag = _txt(valores, "a:IssRetido") == "1"
    iss = _decimal(_txt(valores, "a:ValorIss")) if iss_retido_flag else Decimal("0")
    irrf = _decimal(_txt(valores, "a:ValorIr"))
    pis = _decimal(_txt(valores, "a:ValorPis"))
    cofins = _decimal(_txt(valores, "a:ValorCofins"))
    csll = _decimal(_txt(valores, "a:ValorCsll"))

    discriminacao = _txt(inf, "a:Servico/a:Discriminacao")

    # Prestador
    cnpj_prest = _digits(_txt(inf, "a:PrestadorServico/a:IdentificacaoPrestador/a:Cnpj"))
    if len(cnpj_prest) != 14:
        raise NFSeParseError(f"CNPJ prestador inválido: {cnpj_prest!r}")

    # Tomador (CPF ou CNPJ)
    tomador_cnpj = _digits(_txt(inf, "a:TomadorServico/a:IdentificacaoTomador/a:CpfCnpj/a:Cnpj"))
    tomador_cpf = _digits(_txt(inf, "a:TomadorServico/a:IdentificacaoTomador/a:CpfCnpj/a:Cpf"))
    tomador_doc = tomador_cnpj or tomador_cpf
    if not tomador_doc:
        raise NFSeParseError("Tomador sem CPF/CNPJ")
    tomador_nome = _txt(inf, "a:TomadorServico/a:RazaoSocial")

    # Cancelamento
    canc = root.find(".//a:NfseCancelamento/a:Confirmacao/a:DataHora", _NS) \
        or root.find(".//NfseCancelamento/Confirmacao/DataHora")
    cancelada = canc is not None and canc.text is not None
    data_cancelamento = None
    if cancelada:
        try:
            data_cancelamento = datetime.fromisoformat(canc.text.strip())
        except Exception:
            data_cancelamento = None

    return NFSeData(
        cnpj_prestador=cnpj_prest,
        numero=numero,
        serie=None,
        codigo_verificacao=codigo_ver,
        competencia=competencia,
        data_emissao=data_emissao,
        tomador_doc=tomador_doc,
        tomador_nome=tomador_nome,
        valor_servicos=valor_servicos,
        iss_retido=iss,
        irrf=irrf,
        pis=pis,
        cofins=cofins,
        csll=csll,
        discriminacao=discriminacao,
        cancelada=cancelada,
        data_cancelamento=data_cancelamento,
        xml_raw=xml,
    )
```

- [x] **Step 5: Rodar testes — devem passar**

```powershell
pytest tests/test_nfse_parser.py -v
```

Esperado: 6 passed.

- [x] **Step 6: Commit**

```bash
git add backend/app/services/nfse_parser.py backend/tests/test_nfse_parser.py backend/tests/fixtures/nfse
git commit -m "feat(nfse): parser ABRASF XML + fixtures (PJ, PF, cancelada, retencoes, XXE)"
```

---

### Task 9: Matcher NF↔contrato (TDD)

**Files:**
- Create: `backend/tests/test_nfse_matcher.py`
- Create: `backend/app/services/nfse_matcher.py`

- [ ] **Step 1: Escrever testes**

```python
# backend/tests/test_nfse_matcher.py
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.services.nfse_matcher import MatchResult, MatchStatus, match_nfse


@dataclass
class FakeContract:
    contract_id: str
    cliente_docs: list[str]
    data_inicio: date
    data_fim: date | None = None


def _nf(tomador_doc="98765432000100", competencia=date(2026, 5, 1), discriminacao=None):
    from app.models.nfse import NFSeData

    return NFSeData(
        cnpj_prestador="12345678000199",
        numero="1",
        competencia=competencia,
        data_emissao=competencia,
        tomador_doc=tomador_doc,
        valor_servicos=Decimal("1000"),
        discriminacao=discriminacao,
        xml_raw=b"x",
    )


def test_um_contrato_match_auto():
    cs = [FakeContract("abc12345", ["98765432000100"], date(2025, 1, 1))]
    r = match_nfse(_nf(), cs)
    assert r.status == MatchStatus.AUTO
    assert r.contract_id == "abc12345"


def test_zero_contratos_sem_match():
    r = match_nfse(_nf(), [])
    assert r.status == MatchStatus.SEM_MATCH


def test_contrato_encerrado_antes_da_competencia_ignora():
    cs = [FakeContract("abc12345", ["98765432000100"], date(2024, 1, 1), data_fim=date(2026, 4, 30))]
    r = match_nfse(_nf(), cs)
    assert r.status == MatchStatus.SEM_MATCH


def test_dois_contratos_sem_id_discriminacao_pendente():
    cs = [
        FakeContract("aaaaaaaa", ["98765432000100"], date(2025, 1, 1)),
        FakeContract("bbbbbbbb", ["98765432000100"], date(2025, 6, 1)),
    ]
    r = match_nfse(_nf(discriminacao="Servicos maio"), cs)
    assert r.status == MatchStatus.PENDENTE
    assert set(r.candidatos) == {"aaaaaaaa", "bbbbbbbb"}


def test_dois_contratos_com_id_discriminacao_resolve():
    cs = [
        FakeContract("aaaaaaaa", ["98765432000100"], date(2025, 1, 1)),
        FakeContract("bbbbbbbb", ["98765432000100"], date(2025, 6, 1)),
    ]
    r = match_nfse(_nf(discriminacao="Ref #bbbbbbbb maio"), cs)
    assert r.status == MatchStatus.AUTO
    assert r.contract_id == "bbbbbbbb"


def test_pf_tomador_casa_por_cpf():
    cs = [FakeContract("xyz12345", ["12345678901"], date(2025, 1, 1))]
    r = match_nfse(_nf(tomador_doc="12345678901"), cs)
    assert r.status == MatchStatus.AUTO


def test_normaliza_discriminacao_case_insensitive():
    cs = [
        FakeContract("aaaaaaaa", ["98765432000100"], date(2025, 1, 1)),
        FakeContract("bbbbbbbb", ["98765432000100"], date(2025, 1, 1)),
    ]
    r = match_nfse(_nf(discriminacao="REF #BBBBBBBB"), cs)
    assert r.status == MatchStatus.AUTO
    assert r.contract_id == "bbbbbbbb"
```

- [ ] **Step 2: Rodar e ver falha**

```powershell
pytest tests/test_nfse_matcher.py -v
```

Esperado: import error.

- [ ] **Step 3: Implementar matcher**

```python
# backend/app/services/nfse_matcher.py
"""Casa NF↔contrato: CNPJ/CPF + período, fallback discriminação `#contract_id`."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Protocol


class _ContractLike(Protocol):
    contract_id: str
    cliente_docs: list[str]
    data_inicio: object  # date
    data_fim: object | None


class MatchStatus(str, Enum):
    AUTO = "auto"
    PENDENTE = "pendente"
    SEM_MATCH = "sem_match"


@dataclass
class MatchResult:
    status: MatchStatus
    contract_id: str | None = None
    candidatos: list[str] = field(default_factory=list)
    motivo: str | None = None


_ID_REGEX = re.compile(r"#?\b([a-f0-9-]{8,36})\b")


def _candidatos(nf, contratos: Iterable[_ContractLike]) -> list[_ContractLike]:
    out = []
    for c in contratos:
        if nf.tomador_doc not in (c.cliente_docs or []):
            continue
        if c.data_inicio > nf.competencia:
            continue
        if c.data_fim is not None and c.data_fim < nf.competencia:
            continue
        out.append(c)
    return out


def _ids_na_discriminacao(texto: str | None) -> set[str]:
    if not texto:
        return set()
    return {m.lower() for m in _ID_REGEX.findall(texto.lower())}


def match_nfse(nf, contratos: Iterable[_ContractLike]) -> MatchResult:
    cands = _candidatos(nf, contratos)
    if not cands:
        return MatchResult(MatchStatus.SEM_MATCH, motivo="nenhum contrato elegível")
    if len(cands) == 1:
        return MatchResult(MatchStatus.AUTO, contract_id=cands[0].contract_id)
    ids = _ids_na_discriminacao(nf.discriminacao)
    if ids:
        hits = [c for c in cands if c.contract_id.lower() in ids]
        if len(hits) == 1:
            return MatchResult(MatchStatus.AUTO, contract_id=hits[0].contract_id, motivo="resolvido por #id")
    return MatchResult(
        MatchStatus.PENDENTE,
        candidatos=[c.contract_id for c in cands],
        motivo=f"{len(cands)} contratos candidatos sem desambiguação",
    )
```

- [ ] **Step 4: Rodar testes — devem passar**

```powershell
pytest tests/test_nfse_matcher.py -v
```

Esperado: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/nfse_matcher.py backend/tests/test_nfse_matcher.py
git commit -m "feat(nfse): matcher NF<->contrato (CNPJ/CPF+periodo, fallback #id)"
```

---

### Task 10: Bridge p/ Participação (`nfse_pagamento`) (TDD)

**Files:**
- Create: `backend/tests/test_nfse_pagamento.py`
- Create: `backend/app/services/nfse_pagamento.py`

- [ ] **Step 1: Escrever teste**

```python
# backend/tests/test_nfse_pagamento.py
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.nfse_db import NFSeRecebidaDB  # noqa: F401 -- load metadata


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    with Session() as s:
        yield s


def _seed_contrato_participacao(db):
    db.execute(text("""
        INSERT INTO contracts (contract_id, status, client_name, client_email,
                               current_version, cliente_docs, created_at, updated_at)
        VALUES ('c-1', 'ativo', 'X', 'x@x.com', 1, '["98765432000100"]', '2026-01-01', '2026-01-01')
    """))
    db.execute(text("""
        INSERT INTO participacoes (contract_id, beneficiario_email, beneficiario_nome,
                                   tipo_honorario, percentual_captacao, percentual_performance,
                                   natureza, cliente_cpf_cnpj, data_inicio, vinculo_ativo,
                                   aprovada, created_at, updated_at)
        VALUES ('c-1', 'b@x.com', 'B', 'mensalidade', 10, 0, 'contratual',
                '98765432000100', '2024-08-01', 1, 1, '2026-01-01', '2026-01-01')
    """))
    db.commit()
    return db.execute(text("SELECT id FROM participacoes WHERE contract_id='c-1'")).scalar()


def test_registra_pagamento_e_vincula(db):
    from app.services.nfse_pagamento import gerar_pagamento_para_nfse

    part_id = _seed_contrato_participacao(db)
    # cria NF recebida
    db.execute(text("""
        INSERT INTO nfse_recebidas (cnpj_prestador, numero, competencia, data_emissao,
                                    tomador_doc, valor_servicos, valor_liquido,
                                    xml_raw, status_matching, contract_id, participacao_id)
        VALUES ('12345678000199', '1', '2026-05-01', '2026-05-10',
                '98765432000100', 1000, 970, x'00', 'auto', 'c-1', :pid)
    """), {"pid": part_id})
    db.commit()
    nfse_id = db.execute(text("SELECT id FROM nfse_recebidas LIMIT 1")).scalar()

    result = gerar_pagamento_para_nfse(db, nfse_id=nfse_id)
    assert result.pagamento_id is not None

    row = db.execute(text("SELECT pagamento_id FROM nfse_recebidas WHERE id=:i"),
                     {"i": nfse_id}).fetchone()
    assert row[0] == result.pagamento_id


def test_idempotente_nao_duplica(db):
    from app.services.nfse_pagamento import gerar_pagamento_para_nfse

    part_id = _seed_contrato_participacao(db)
    db.execute(text("""
        INSERT INTO nfse_recebidas (cnpj_prestador, numero, competencia, data_emissao,
                                    tomador_doc, valor_servicos, valor_liquido,
                                    xml_raw, status_matching, contract_id, participacao_id)
        VALUES ('12345678000199', '2', '2026-05-01', '2026-05-10',
                '98765432000100', 500, 485, x'00', 'auto', 'c-1', :pid)
    """), {"pid": part_id})
    db.commit()
    nfse_id = db.execute(text("SELECT id FROM nfse_recebidas LIMIT 1")).scalar()

    r1 = gerar_pagamento_para_nfse(db, nfse_id=nfse_id)
    r2 = gerar_pagamento_para_nfse(db, nfse_id=nfse_id)
    assert r1.pagamento_id == r2.pagamento_id
    n_pagamentos = db.execute(text("SELECT COUNT(*) FROM participacao_pagamentos")).scalar()
    assert n_pagamentos == 1
```

- [ ] **Step 2: Rodar e ver falha**

```powershell
pytest tests/test_nfse_pagamento.py -v
```

Esperado: import error.

- [ ] **Step 3: Implementar bridge**

```python
# backend/app/services/nfse_pagamento.py
"""Cria registro em participacao_pagamentos para uma NFSe vinculada.

Idempotente: se NFSe.pagamento_id já existe, retorna sem criar duplicata.
Calcula valor_participacao = valor_liquido * percentual_total / 100.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class PagamentoResult:
    nfse_id: int
    pagamento_id: int | None
    motivo: str | None = None


def gerar_pagamento_para_nfse(db: Session, nfse_id: int) -> PagamentoResult:
    row = db.execute(
        text("""
            SELECT id, participacao_id, pagamento_id, valor_liquido, data_emissao, status_matching
            FROM nfse_recebidas WHERE id = :i
        """),
        {"i": nfse_id},
    ).fetchone()
    if row is None:
        raise ValueError(f"NFSe {nfse_id} não encontrada")
    _, participacao_id, pagamento_id, valor_liquido, data_emissao, status = row

    if pagamento_id:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=pagamento_id, motivo="ja_vinculada")
    if not participacao_id:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=None, motivo="sem_participacao")

    part = db.execute(
        text("""
            SELECT percentual_captacao, percentual_performance, vinculo_ativo
            FROM participacoes WHERE id = :i
        """),
        {"i": participacao_id},
    ).fetchone()
    if part is None:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=None, motivo="participacao_inexistente")
    pct_cap, pct_perf, ativo = part
    if not ativo:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=None, motivo="vinculo_inativo")

    pct_total = Decimal(str(pct_cap or 0)) + Decimal(str(pct_perf or 0))
    valor_part = (Decimal(str(valor_liquido)) * pct_total / Decimal("100")).quantize(Decimal("0.01"))

    db.execute(
        text("""
            INSERT INTO participacao_pagamentos (
                participacao_id, data_recebimento, valor_liquido_recebido,
                valor_participacao, dentro_limite_temporal, observacoes,
                registrado_por, created_at
            ) VALUES (
                :pid, :dt, :vl, :vp, 1, 'NFS-e auto', 'sistema', :now
            )
        """),
        {
            "pid": participacao_id,
            "dt": data_emissao,
            "vl": float(valor_liquido),
            "vp": float(valor_part),
            "now": datetime.now(timezone.utc),
        },
    )
    new_id = db.execute(text("SELECT last_insert_rowid()")).scalar() \
        if db.bind.dialect.name == "sqlite" \
        else db.execute(text("SELECT lastval()")).scalar()

    db.execute(
        text("UPDATE nfse_recebidas SET pagamento_id = :p, atualizado_em = :now WHERE id = :i"),
        {"p": new_id, "now": datetime.now(timezone.utc), "i": nfse_id},
    )
    db.commit()
    return PagamentoResult(nfse_id=nfse_id, pagamento_id=new_id)
```

- [ ] **Step 4: Rodar testes — devem passar**

```powershell
pytest tests/test_nfse_pagamento.py -v
```

Esperado: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/nfse_pagamento.py backend/tests/test_nfse_pagamento.py
git commit -m "feat(nfse): bridge nfse_pagamento -> participacao_pagamentos (idempotente)"
```

---

## Phase 3 — Sync orchestrator

### Task 11: `nfse_sync.ingest_payload` (TDD)

**Files:**
- Create: `backend/tests/test_nfse_sync_orchestrator.py`
- Create: `backend/app/services/nfse_sync.py`

- [ ] **Step 1: Escrever teste**

```python
# backend/tests/test_nfse_sync_orchestrator.py
import base64
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.nfse_db import NFSeRecebidaDB  # noqa: F401 -- ensures metadata loaded

FIXTURES = Path(__file__).parent / "fixtures" / "nfse"


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    with Session() as s:
        # seed: 1 contrato c/ doc tomador da NF mínima
        s.execute(text("""
            INSERT INTO contracts (contract_id, status, client_name, client_email,
                                   current_version, cliente_docs, created_at, updated_at)
            VALUES ('c-1', 'ativo', 'X', 'x@x.com', 1, '["98765432000100"]', '2026-01-01', '2026-01-01')
        """))
        s.execute(text("""
            INSERT INTO participacoes (contract_id, beneficiario_email, beneficiario_nome,
                                       tipo_honorario, percentual_captacao, percentual_performance,
                                       natureza, cliente_cpf_cnpj, data_inicio, vinculo_ativo,
                                       aprovada, created_at, updated_at)
            VALUES ('c-1', 'b@x.com', 'B', 'mensalidade', 10, 0, 'contratual',
                    '98765432000100', '2024-08-01', 1, 1, '2026-01-01', '2026-01-01')
        """))
        s.commit()
        yield s


def test_ingest_uma_nf_auto_vinculada(db):
    from app.services.nfse_sync import ingest_payload

    xml = (FIXTURES / "abrasf_minimo.xml").read_bytes()
    job = ingest_payload(
        db,
        cnpj_prestador="12345678000199",
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
        origem="manual",
        disparado_por="teste@x",
        xmls=[xml],
    )
    assert job.status == "ok"
    assert job.total_nfs == 1
    assert job.auto_vinculadas == 1
    assert job.pendentes == 0
    nf = db.execute(text("SELECT status_matching, contract_id, pagamento_id FROM nfse_recebidas")).fetchone()
    assert nf[0] == "auto"
    assert nf[1] == "c-1"
    assert nf[2] is not None


def test_idempotencia_segunda_chamada_nao_duplica(db):
    from app.services.nfse_sync import ingest_payload

    xml = (FIXTURES / "abrasf_minimo.xml").read_bytes()
    ingest_payload(db, cnpj_prestador="12345678000199",
                   periodo_inicio=date(2026, 5, 1), periodo_fim=date(2026, 5, 31),
                   origem="cron", disparado_por=None, xmls=[xml])
    ingest_payload(db, cnpj_prestador="12345678000199",
                   periodo_inicio=date(2026, 5, 1), periodo_fim=date(2026, 5, 31),
                   origem="cron", disparado_por=None, xmls=[xml])
    n = db.execute(text("SELECT COUNT(*) FROM nfse_recebidas")).scalar()
    assert n == 1
    n_pag = db.execute(text("SELECT COUNT(*) FROM participacao_pagamentos")).scalar()
    assert n_pag == 1


def test_xml_malformado_conta_como_erro(db):
    from app.services.nfse_sync import ingest_payload

    job = ingest_payload(db, cnpj_prestador="12345678000199",
                        periodo_inicio=date(2026, 5, 1), periodo_fim=date(2026, 5, 31),
                        origem="manual", disparado_por=None,
                        xmls=[b"<not><valid"])
    assert job.erros == 1
    assert job.total_nfs == 0


def test_cancelamento_detectado(db):
    from app.services.nfse_sync import ingest_payload

    xml = (FIXTURES / "abrasf_cancelada.xml").read_bytes()
    job = ingest_payload(db, cnpj_prestador="12345678000199",
                        periodo_inicio=date(2026, 5, 1), periodo_fim=date(2026, 5, 31),
                        origem="manual", disparado_por=None, xmls=[xml])
    assert job.total_nfs == 1
    row = db.execute(text("SELECT cancelada, status_matching FROM nfse_recebidas")).fetchone()
    assert row[0] == 1  # SQLite armazena bool como int
    assert row[1] == "cancelada"
```

- [ ] **Step 2: Rodar e ver falha**

```powershell
pytest tests/test_nfse_sync_orchestrator.py -v
```

Esperado: import error.

- [ ] **Step 3: Implementar orchestrator**

```python
# backend/app/services/nfse_sync.py
"""Orquestrador: recebe XMLs, parseia, persiste, casa, gera pagamento."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.nfse_matcher import MatchStatus, match_nfse
from app.services.nfse_pagamento import gerar_pagamento_para_nfse
from app.services.nfse_parser import NFSeParseError, parse_nfse_xml


@dataclass
class JobOutcome:
    status: str
    total_nfs: int
    auto_vinculadas: int
    pendentes: int
    sem_match: int
    erros: int
    motivo_falha: str | None = None


def _contratos_candidatos(db: Session, tomador_doc: str) -> list:
    rows = db.execute(
        text("""
            SELECT c.contract_id, c.cliente_docs,
                   MIN(p.data_inicio) AS data_inicio,
                   MAX(CASE WHEN p.vinculo_ativo=1 THEN NULL ELSE p.data_fim_vinculo END) AS data_fim
            FROM contracts c
            LEFT JOIN participacoes p ON p.contract_id = c.contract_id
            WHERE c.cliente_docs LIKE :pat
            GROUP BY c.contract_id, c.cliente_docs
        """),
        {"pat": f'%"{tomador_doc}"%'},
    ).fetchall()

    class _C:
        def __init__(self, cid, docs_json, data_inicio, data_fim):
            self.contract_id = cid
            self.cliente_docs = json.loads(docs_json or "[]")
            self.data_inicio = data_inicio if isinstance(data_inicio, date) else (
                date.fromisoformat(data_inicio) if data_inicio else date(2024, 8, 1)
            )
            self.data_fim = data_fim if (isinstance(data_fim, date) or data_fim is None) else (
                date.fromisoformat(data_fim) if data_fim else None
            )

    return [_C(*r) for r in rows]


def _participacao_ativa_do_contrato(db: Session, contract_id: str) -> int | None:
    row = db.execute(
        text("""
            SELECT id FROM participacoes
            WHERE contract_id = :c AND vinculo_ativo = 1 AND aprovada = 1
            ORDER BY data_inicio DESC LIMIT 1
        """),
        {"c": contract_id},
    ).fetchone()
    return row[0] if row else None


def _create_job(db, cnpj, origem, disparado_por, ini, fim) -> int:
    now = datetime.now(timezone.utc)
    db.execute(
        text("""
            INSERT INTO sync_jobs (cnpj_prestador, origem, disparado_por,
                                   iniciado_em, periodo_inicio, periodo_fim, status)
            VALUES (:c, :o, :u, :n, :i, :f, 'em_andamento')
        """),
        {"c": cnpj, "o": origem, "u": disparado_por, "n": now, "i": ini, "f": fim},
    )
    db.commit()
    return db.execute(text("SELECT last_insert_rowid()") if db.bind.dialect.name == "sqlite"
                      else text("SELECT lastval()")).scalar()


def _finalize_job(db, job_id, outcome: JobOutcome):
    db.execute(
        text("""
            UPDATE sync_jobs
            SET finalizado_em = :n, total_nfs = :t, auto_vinculadas = :a,
                pendentes = :p, sem_match = :s, erros = :e,
                status = :st, motivo_falha = :mf
            WHERE id = :id
        """),
        {
            "n": datetime.now(timezone.utc),
            "t": outcome.total_nfs, "a": outcome.auto_vinculadas,
            "p": outcome.pendentes, "s": outcome.sem_match, "e": outcome.erros,
            "st": outcome.status, "mf": outcome.motivo_falha,
            "id": job_id,
        },
    )
    db.commit()


def ingest_payload(
    db: Session,
    *,
    cnpj_prestador: str,
    periodo_inicio: date,
    periodo_fim: date,
    origem: str,
    disparado_por: str | None,
    xmls: Iterable[bytes],
) -> JobOutcome:
    job_id = _create_job(db, cnpj_prestador, origem, disparado_por, periodo_inicio, periodo_fim)
    total = auto = pend = sem = errs = 0

    for xml in xmls:
        try:
            nf = parse_nfse_xml(xml)
        except NFSeParseError:
            errs += 1
            continue

        # upsert por (cnpj_prestador, numero, serie)
        existing = db.execute(
            text("""
                SELECT id, cancelada FROM nfse_recebidas
                WHERE cnpj_prestador = :c AND numero = :n
                  AND (serie IS :s OR serie = :s)
            """),
            {"c": nf.cnpj_prestador, "n": nf.numero, "s": nf.serie},
        ).fetchone()

        if existing:
            nfse_id, was_cancelada = existing
            if nf.cancelada and not was_cancelada:
                db.execute(
                    text("""
                        UPDATE nfse_recebidas
                        SET cancelada = 1, data_cancelamento = :d,
                            status_matching = 'cancelada',
                            atualizado_em = :n, motivo = 'cancelada pelo prestador'
                        WHERE id = :i
                    """),
                    {"d": nf.data_cancelamento, "n": datetime.now(timezone.utc), "i": nfse_id},
                )
                db.commit()
                total += 1
            continue

        # Inserir nova
        candidatos = _contratos_candidatos(db, nf.tomador_doc)
        r = match_nfse(nf, candidatos)

        contract_id = r.contract_id
        participacao_id = _participacao_ativa_do_contrato(db, contract_id) if contract_id else None

        status = "cancelada" if nf.cancelada else r.status.value
        if nf.cancelada:
            pend += 0  # canceladas não contam pendentes
        elif r.status == MatchStatus.AUTO:
            auto += 1
        elif r.status == MatchStatus.PENDENTE:
            pend += 1
        else:
            sem += 1

        db.execute(
            text("""
                INSERT INTO nfse_recebidas (
                    cnpj_prestador, numero, serie, codigo_verificacao,
                    competencia, data_emissao, tomador_doc, tomador_nome,
                    valor_servicos, iss_retido, irrf, pis, cofins, csll,
                    valor_liquido, discriminacao, cancelada, data_cancelamento,
                    xml_raw, contract_id, participacao_id, status_matching, motivo
                ) VALUES (
                    :cnpj, :num, :ser, :cv,
                    :cmp, :em, :td, :tn,
                    :vs, :iss, :ir, :pis, :co, :cs,
                    :vl, :dis, :canc, :dc,
                    :xml, :cid, :pid, :st, :mot
                )
            """),
            {
                "cnpj": nf.cnpj_prestador, "num": nf.numero, "ser": nf.serie,
                "cv": nf.codigo_verificacao,
                "cmp": nf.competencia, "em": nf.data_emissao,
                "td": nf.tomador_doc, "tn": nf.tomador_nome,
                "vs": float(nf.valor_servicos), "iss": float(nf.iss_retido),
                "ir": float(nf.irrf), "pis": float(nf.pis),
                "co": float(nf.cofins), "cs": float(nf.csll),
                "vl": float(nf.valor_liquido), "dis": nf.discriminacao,
                "canc": 1 if nf.cancelada else 0, "dc": nf.data_cancelamento,
                "xml": nf.xml_raw, "cid": contract_id, "pid": participacao_id,
                "st": status, "mot": r.motivo,
            },
        )
        db.commit()
        total += 1

        if not nf.cancelada and r.status == MatchStatus.AUTO and participacao_id:
            new_id = db.execute(text("SELECT id FROM nfse_recebidas ORDER BY id DESC LIMIT 1")).scalar()
            gerar_pagamento_para_nfse(db, nfse_id=new_id)

    outcome = JobOutcome(
        status="ok",
        total_nfs=total, auto_vinculadas=auto, pendentes=pend,
        sem_match=sem, erros=errs,
    )
    _finalize_job(db, job_id, outcome)
    return outcome
```

- [ ] **Step 4: Rodar testes — devem passar**

```powershell
pytest tests/test_nfse_sync_orchestrator.py -v
```

Esperado: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/nfse_sync.py backend/tests/test_nfse_sync_orchestrator.py
git commit -m "feat(nfse): orquestrador ingest_payload (parse->match->payment, idempotente)"
```

---

### Task 12: Lock por CNPJ + race condition em pagamento

**Files:**
- Modify: `backend/app/services/nfse_sync.py`

- [ ] **Step 1: Escrever teste de concorrência**

Adicionar em `backend/tests/test_nfse_sync_orchestrator.py`:

```python
def test_lock_concorrente_segunda_chamada_e_no_op(db):
    """2 chamadas paralelas mesma janela: 2ª retorna ja_rodando."""
    from app.services.nfse_sync import ingest_payload, JobLockError

    # Simula lock criando job em_andamento manualmente
    from sqlalchemy import text
    from datetime import datetime, timezone
    db.execute(text("""
        INSERT INTO sync_jobs (cnpj_prestador, origem, iniciado_em,
                               periodo_inicio, periodo_fim, status)
        VALUES ('12345678000199', 'cron', :n, '2026-05-01', '2026-05-31', 'em_andamento')
    """), {"n": datetime.now(timezone.utc)})
    db.commit()

    with pytest.raises(JobLockError):
        ingest_payload(
            db, cnpj_prestador="12345678000199",
            periodo_inicio=date(2026, 5, 1), periodo_fim=date(2026, 5, 31),
            origem="cron", disparado_por=None, xmls=[],
        )
```

- [ ] **Step 2: Rodar — falha**

```powershell
pytest tests/test_nfse_sync_orchestrator.py::test_lock_concorrente_segunda_chamada_e_no_op -v
```

Esperado: `JobLockError` não existe.

- [ ] **Step 3: Adicionar lock em `nfse_sync.py`**

Adicionar perto do topo do arquivo:

```python
class JobLockError(Exception):
    """Outro sync ainda em andamento p/ mesmo CNPJ."""
```

E no início de `ingest_payload`, antes de `_create_job`:

```python
    em_andamento = db.execute(
        text("""
            SELECT id FROM sync_jobs
            WHERE cnpj_prestador = :c AND status = 'em_andamento'
            ORDER BY iniciado_em DESC LIMIT 1
        """),
        {"c": cnpj_prestador},
    ).fetchone()
    if em_andamento:
        raise JobLockError(f"sync_job {em_andamento[0]} ainda em andamento")
```

- [ ] **Step 4: Rodar teste — passa**

```powershell
pytest tests/test_nfse_sync_orchestrator.py -v
```

Esperado: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/nfse_sync.py backend/tests/test_nfse_sync_orchestrator.py
git commit -m "feat(nfse): lock por CNPJ no ingest_payload (JobLockError em conflito)"
```

---

### Task 13: Endpoint `/api/nfse/health` (público)

**Files:**
- Create: `backend/app/routers/nfse.py` (stub apenas health p/ agora)
- Modify: `backend/app/main.py`

- [ ] **Step 1: Criar router stub**

```python
# backend/app/routers/nfse.py
"""Endpoints públicos NFS-e (health agora; lista/vincular nas próximas tasks)."""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal

router = APIRouter(prefix="/api/nfse", tags=["nfse"])


@router.get("/health")
def nfse_health() -> dict:
    """Estado da feature NFS-e. Público, sem segredos no payload."""
    if not settings.nfse_enabled:
        return {"enabled": False}

    with SessionLocal() as db:
        last = db.execute(text("""
            SELECT iniciado_em, finalizado_em, status, total_nfs, erros
            FROM sync_jobs
            ORDER BY iniciado_em DESC LIMIT 1
        """)).fetchone()
    return {
        "enabled": True,
        "last_job": None if last is None else {
            "iniciado_em": last[0].isoformat() if last[0] else None,
            "finalizado_em": last[1].isoformat() if last[1] else None,
            "status": last[2],
            "total_nfs": last[3],
            "erros": last[4],
        },
        "now": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 2: Wire em `main.py`**

Em `backend/app/main.py`, adicionar à lista de imports:

```python
from app.routers import cnpj, contract, contracts, docuseal, email, nfse, participacoes, users
```

E adicionar após os outros `include_router`:

```python
app.include_router(nfse.router)
```

- [ ] **Step 3: Smoke**

```powershell
cd backend
uvicorn app.main:app --port 8000 &
curl http://localhost:8000/api/nfse/health
```

Esperado (com `NFSE_ENABLED=false`): `{"enabled":false}`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/nfse.py backend/app/main.py
git commit -m "feat(nfse): router nfse + endpoint /api/nfse/health"
```

---

## Phase 4 — Routers (admin, worker, financeiro)

### Task 14: Router admin — upload de credencial PBH

**Files:**
- Create: `backend/app/routers/admin_credenciais.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implementar router**

```python
# backend/app/routers/admin_credenciais.py
"""Admin: upload e gerenciamento de credencial PBH."""
from __future__ import annotations

from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models.nfse import CredencialPbhCreate, CredencialPbhOut
from app.services.crypto import CryptoBox

router = APIRouter(prefix="/api/admin/credencial-pbh", tags=["admin-nfse"])


def _require_admin(user=Depends(get_current_user)):
    if (user.get("role") if isinstance(user, dict) else getattr(user, "role", None)) != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas admin")
    return user


def _ensure_enabled():
    if not settings.nfse_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NFS-e desabilitado")
    if not settings.nfse_kek:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "NFSE_KEK não configurada")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


@router.post("", response_model=CredencialPbhOut, status_code=201)
def upsert_credencial(body: CredencialPbhCreate,
                      db: Session = Depends(get_db),
                      user=Depends(_require_admin)):
    _ensure_enabled()
    cnpj = _digits(body.cnpj_prestador)
    if len(cnpj) != 14:
        raise HTTPException(400, "CNPJ inválido")

    box = CryptoBox(settings.nfse_kek)
    login_blob = box.encrypt(body.login)
    senha_blob = box.encrypt(body.senha)
    now = datetime.now(timezone.utc)
    user_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", "admin")

    existing = db.execute(
        text("SELECT id FROM credencial_pbh WHERE cnpj_prestador = :c"),
        {"c": cnpj},
    ).fetchone()

    if existing:
        cid = existing[0]
        db.execute(
            text("""
                UPDATE credencial_pbh
                SET login_enc=:le, nonce_login=:nl, senha_enc=:se, nonce_senha=:ns,
                    ativo=1, motivo_inativacao=NULL, atualizado_em=:now
                WHERE id=:id
            """),
            {"le": login_blob.ciphertext, "nl": login_blob.nonce,
             "se": senha_blob.ciphertext, "ns": senha_blob.nonce,
             "now": now, "id": cid},
        )
    else:
        db.execute(
            text("""
                INSERT INTO credencial_pbh (cnpj_prestador, login_enc, nonce_login,
                                            senha_enc, nonce_senha, ativo,
                                            criado_em, criado_por)
                VALUES (:c, :le, :nl, :se, :ns, 1, :now, :u)
            """),
            {"c": cnpj, "le": login_blob.ciphertext, "nl": login_blob.nonce,
             "se": senha_blob.ciphertext, "ns": senha_blob.nonce,
             "now": now, "u": user_email},
        )
    db.execute(
        text("""
            INSERT INTO nfse_audit_log (acao, user_email, payload_after, ts)
            VALUES ('credencial.upsert', :u, :p, :now)
        """),
        {"u": user_email, "p": '{"cnpj_prestador":"' + cnpj + '"}', "now": now},
    )
    db.commit()

    row = db.execute(
        text("""SELECT id, cnpj_prestador, ativo, criado_em, criado_por, motivo_inativacao
                FROM credencial_pbh WHERE cnpj_prestador=:c"""),
        {"c": cnpj},
    ).fetchone()
    return CredencialPbhOut(
        id=row[0], cnpj_prestador=row[1], ativo=bool(row[2]),
        criado_em=row[3], criado_por=row[4], motivo_inativacao=row[5],
    )


@router.get("", response_model=list[CredencialPbhOut])
def listar(db: Session = Depends(get_db), user=Depends(_require_admin)):
    _ensure_enabled()
    rows = db.execute(
        text("""SELECT id, cnpj_prestador, ativo, criado_em, criado_por, motivo_inativacao
                FROM credencial_pbh ORDER BY criado_em DESC""")
    ).fetchall()
    return [
        CredencialPbhOut(id=r[0], cnpj_prestador=r[1], ativo=bool(r[2]),
                        criado_em=r[3], criado_por=r[4], motivo_inativacao=r[5])
        for r in rows
    ]


@router.post("/{cnpj}/desativar", response_model=CredencialPbhOut)
def desativar(cnpj: str, motivo: str = "",
              db: Session = Depends(get_db), user=Depends(_require_admin)):
    _ensure_enabled()
    cnpj = _digits(cnpj)
    now = datetime.now(timezone.utc)
    user_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", "admin")
    db.execute(
        text("""UPDATE credencial_pbh SET ativo=0, motivo_inativacao=:m, atualizado_em=:n
                WHERE cnpj_prestador=:c"""),
        {"m": motivo or "manual", "n": now, "c": cnpj},
    )
    db.execute(
        text("INSERT INTO nfse_audit_log (acao, user_email, ts) VALUES ('credencial.desativar', :u, :n)"),
        {"u": user_email, "n": now},
    )
    db.commit()
    row = db.execute(
        text("""SELECT id, cnpj_prestador, ativo, criado_em, criado_por, motivo_inativacao
                FROM credencial_pbh WHERE cnpj_prestador=:c"""),
        {"c": cnpj},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Credencial não encontrada")
    return CredencialPbhOut(id=row[0], cnpj_prestador=row[1], ativo=bool(row[2]),
                           criado_em=row[3], criado_por=row[4], motivo_inativacao=row[5])
```

- [ ] **Step 2: Wire em `main.py`**

```python
from app.routers import admin_credenciais  # add to imports
# ...
app.include_router(admin_credenciais.router)
```

- [ ] **Step 3: Smoke**

```powershell
# Definir env temporário
$env:NFSE_ENABLED="true"
$env:NFSE_KEK=python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
uvicorn app.main:app --port 8000 &
curl -X POST http://localhost:8000/api/admin/credencial-pbh `
  -H "X-Dev-User-Email: admin@teste.local" -H "X-Dev-User-Role: admin" `
  -H "Content-Type: application/json" `
  -d '{\"cnpj_prestador\":\"12345678000199\",\"login\":\"u\",\"senha\":\"p\"}'
```

Esperado: 201 c/ payload da credencial.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/admin_credenciais.py backend/app/main.py
git commit -m "feat(nfse): router admin credencial PBH (upsert/list/desativar) + audit log"
```

---

### Task 15: Router worker interno (token-only)

**Files:**
- Create: `backend/app/routers/nfse_internal.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implementar router**

```python
# backend/app/routers/nfse_internal.py
"""Endpoints do worker (GitHub Actions). Bearer token NFSE_WORKER_TOKEN.

- GET /api/nfse/credenciais/{cnpj}  → retorna {login,senha} HTTPS
- POST /api/nfse/ingest             → recebe lote de XMLs
"""
from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.nfse import IngestRequest, SyncJobOut
from app.services.crypto import CryptoBox, InvalidCipherError
from app.services.nfse_sync import JobLockError, ingest_payload

router = APIRouter(prefix="/api/nfse", tags=["nfse-internal"])


def _require_worker(authorization: str = Header(default="")):
    if not settings.nfse_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NFS-e desabilitado")
    if not settings.nfse_worker_token:
        raise HTTPException(500, "NFSE_WORKER_TOKEN não configurado")
    expected = f"Bearer {settings.nfse_worker_token}"
    if authorization != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido")
    return True


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


@router.get("/credenciais/{cnpj}")
def fetch_credencial(cnpj: str, _: bool = Depends(_require_worker),
                     db: Session = Depends(get_db)):
    cnpj = _digits(cnpj)
    row = db.execute(
        text("""SELECT login_enc, nonce_login, senha_enc, nonce_senha, ativo
                FROM credencial_pbh WHERE cnpj_prestador=:c"""),
        {"c": cnpj},
    ).fetchone()
    if not row:
        raise HTTPException(404, "credencial não encontrada")
    le, nl, se, ns, ativo = row
    if not ativo:
        raise HTTPException(409, "credencial inativa")
    box = CryptoBox(settings.nfse_kek)
    try:
        from app.services.crypto import EncryptedBlob
        login = box.decrypt(EncryptedBlob(nonce=nl, ciphertext=le))
        senha = box.decrypt(EncryptedBlob(nonce=ns, ciphertext=se))
    except InvalidCipherError as e:
        raise HTTPException(500, f"falha decrypt: {e}") from e
    return {"login": login, "senha": senha}


@router.post("/ingest", response_model=SyncJobOut)
def ingest(body: IngestRequest, _: bool = Depends(_require_worker),
           db: Session = Depends(get_db)):
    cnpj = _digits(body.cnpj_prestador)
    try:
        xmls = [base64.b64decode(b) for b in body.xmls_b64]
    except binascii.Error as e:
        raise HTTPException(400, f"xml base64 inválido: {e}") from e
    try:
        outcome = ingest_payload(
            db, cnpj_prestador=cnpj,
            periodo_inicio=body.periodo_inicio, periodo_fim=body.periodo_fim,
            origem=body.origem, disparado_por=body.disparado_por,
            xmls=xmls,
        )
    except JobLockError as e:
        raise HTTPException(409, str(e)) from e

    last = db.execute(
        text("SELECT * FROM sync_jobs WHERE cnpj_prestador=:c ORDER BY id DESC LIMIT 1"),
        {"c": cnpj},
    ).fetchone()
    return SyncJobOut(
        id=last.id, cnpj_prestador=last.cnpj_prestador,
        origem=last.origem, iniciado_em=last.iniciado_em,
        finalizado_em=last.finalizado_em,
        periodo_inicio=last.periodo_inicio, periodo_fim=last.periodo_fim,
        total_nfs=last.total_nfs, auto_vinculadas=last.auto_vinculadas,
        pendentes=last.pendentes, sem_match=last.sem_match, erros=last.erros,
        status=last.status, motivo_falha=last.motivo_falha,
    )


@router.post("/sync-status")
def report_status(cnpj_prestador: str, status: str, motivo: str | None = None,
                  _: bool = Depends(_require_worker), db: Session = Depends(get_db)):
    """Worker reporta falhas pré-ingest (login, captcha, layout)."""
    cnpj = _digits(cnpj_prestador)
    now = datetime.now(timezone.utc)
    db.execute(
        text("""
            INSERT INTO sync_jobs (cnpj_prestador, origem, iniciado_em, finalizado_em,
                                   periodo_inicio, periodo_fim, status, motivo_falha)
            VALUES (:c, 'cron', :n, :n, :n, :n, :s, :m)
        """),
        {"c": cnpj, "n": now, "s": status, "m": motivo},
    )
    if status == "erro_login":
        db.execute(
            text("UPDATE credencial_pbh SET ativo=0, motivo_inativacao=:m, atualizado_em=:n WHERE cnpj_prestador=:c"),
            {"m": motivo or "login_invalido", "n": now, "c": cnpj},
        )
    db.commit()
    return {"ok": True}
```

- [ ] **Step 2: Wire em `main.py`**

```python
from app.routers import admin_credenciais, nfse_internal  # adicionar
# ...
app.include_router(nfse_internal.router)
```

- [ ] **Step 3: Smoke**

```powershell
$env:NFSE_WORKER_TOKEN="testtoken"
curl http://localhost:8000/api/nfse/credenciais/12345678000199 `
  -H "Authorization: Bearer testtoken"
```

Esperado: 200 com `{login, senha}` da credencial inserida no Task 14, OU 404 se ainda não inserida.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/nfse_internal.py backend/app/main.py
git commit -m "feat(nfse): router interno (worker bearer): /credenciais, /ingest, /sync-status"
```

---

### Task 16: Router financeiro — listar/vincular/sync

**Files:**
- Modify: `backend/app/routers/nfse.py`

- [ ] **Step 1: Estender `nfse.py` com endpoints do financeiro**

Adicionar a `backend/app/routers/nfse.py` (após o endpoint `/health` existente):

```python
from datetime import date as _date, datetime as _dt, timezone as _tz, timedelta as _td
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.nfse import NFSeOut, SyncJobOut, VincularRequest
from app.services.nfse_pagamento import gerar_pagamento_para_nfse


def _require_financeiro(user=Depends(get_current_user)):
    role = user.get("role") if isinstance(user, dict) else getattr(user, "role", None)
    if role not in ("financeiro", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito ao financeiro")
    return user


@router.get("", response_model=list[NFSeOut])
def listar_nfse(
    cnpj_prestador: Optional[str] = None,
    competencia_mes: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}$"),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(_require_financeiro),
):
    if not settings.nfse_enabled:
        raise HTTPException(404, "NFS-e desabilitado")
    sql = ["SELECT * FROM nfse_recebidas WHERE 1=1"]
    params: dict = {}
    if cnpj_prestador:
        sql.append("AND cnpj_prestador = :c"); params["c"] = cnpj_prestador
    if competencia_mes:
        y, m = map(int, competencia_mes.split("-"))
        ini = _date(y, m, 1)
        fim = (_date(y + (m // 12), (m % 12) + 1, 1) - _td(days=1))
        sql.append("AND competencia BETWEEN :i AND :f"); params["i"] = ini; params["f"] = fim
    if status:
        sql.append("AND status_matching = :s"); params["s"] = status
    sql.append("ORDER BY data_emissao DESC LIMIT 500")
    rows = db.execute(text(" ".join(sql)), params).fetchall()
    return [NFSeOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/{nfse_id}/vincular", response_model=NFSeOut)
def vincular_manual(nfse_id: int, body: VincularRequest,
                    db: Session = Depends(get_db),
                    user=Depends(_require_financeiro)):
    if not settings.nfse_enabled:
        raise HTTPException(404, "NFS-e desabilitado")
    row = db.execute(text("SELECT id, status_matching FROM nfse_recebidas WHERE id=:i"),
                     {"i": nfse_id}).fetchone()
    if not row:
        raise HTTPException(404, "NFS-e não encontrada")
    if row.status_matching == "auto":
        raise HTTPException(409, "NFS-e já vinculada automaticamente; use 'revisar'")

    # confirma contrato existe
    c = db.execute(text("SELECT contract_id FROM contracts WHERE contract_id=:c"),
                   {"c": body.contract_id}).fetchone()
    if not c:
        raise HTTPException(404, "contrato não existe")

    # tenta participação ativa
    part = db.execute(text("""SELECT id FROM participacoes
                              WHERE contract_id=:c AND vinculo_ativo=1 AND aprovada=1
                              ORDER BY data_inicio DESC LIMIT 1"""),
                      {"c": body.contract_id}).fetchone()
    pid = part[0] if part else None

    user_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", "?")
    now = _dt.now(_tz.utc)
    db.execute(text("""UPDATE nfse_recebidas
                       SET contract_id=:c, participacao_id=:p, status_matching='manual',
                           motivo=:m, atualizado_em=:n WHERE id=:i"""),
               {"c": body.contract_id, "p": pid, "m": body.motivo or "vinculo manual",
                "n": now, "i": nfse_id})
    db.execute(text("""INSERT INTO nfse_audit_log (nfse_id, acao, user_email, ts)
                       VALUES (:i, 'nfse.vincular_manual', :u, :n)"""),
               {"i": nfse_id, "u": user_email, "n": now})
    db.commit()

    if pid:
        gerar_pagamento_para_nfse(db, nfse_id=nfse_id)

    out = db.execute(text("SELECT * FROM nfse_recebidas WHERE id=:i"), {"i": nfse_id}).fetchone()
    return NFSeOut.model_validate(out, from_attributes=True)


@router.post("/sync", response_model=dict)
def sync_manual(
    cnpj_prestador: str,
    db: Session = Depends(get_db),
    user=Depends(_require_financeiro),
):
    """Dispara um workflow_dispatch no GitHub Actions (assíncrono).

    Aqui apenas registra intenção; o worker é o GH Actions que poll-a o endpoint.
    Implementação completa do trigger remoto fica fora deste sprint (workflow_dispatch
    pode ser disparado via gh api / webhook). Endpoint registra intent em sync_jobs.
    """
    if not settings.nfse_enabled:
        raise HTTPException(404, "NFS-e desabilitado")
    cnpj = re.sub(r"\D", "", cnpj_prestador)
    now = _dt.now(_tz.utc)
    db.execute(text("""
        INSERT INTO sync_jobs (cnpj_prestador, origem, disparado_por,
                               iniciado_em, periodo_inicio, periodo_fim, status)
        VALUES (:c, 'manual', :u, :n, :n, :n, 'agendado')
    """), {"c": cnpj, "u": user.get("email") if isinstance(user, dict) else getattr(user, "email", "?"),
           "n": now})
    db.commit()
    return {"ok": True, "msg": "sync agendado; GH Actions executará no próximo run ou via dispatch"}
```

Garantir imports no topo do arquivo: `import re`, `from sqlalchemy import text`.

- [ ] **Step 2: Smoke**

```powershell
curl "http://localhost:8000/api/nfse?competencia_mes=2026-05" `
  -H "X-Dev-User-Email: financeiro@teste.local" -H "X-Dev-User-Role: financeiro"
```

Esperado: 200 com array (vazio se DB sem dados).

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/nfse.py
git commit -m "feat(nfse): endpoints financeiro (listar, vincular manual, sync manual)"
```

---

### Task 17: Feature flag e configuração final em `main.py`

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Confirmar inclusão de routers**

Garantir que `backend/app/main.py` tem (após Task 13–16):

```python
from app.routers import (
    admin_credenciais, cnpj, contract, contracts, docuseal, email,
    nfse, nfse_internal, participacoes, users,
)
# ...
app.include_router(nfse.router)
app.include_router(nfse_internal.router)
app.include_router(admin_credenciais.router)
```

- [ ] **Step 2: Smoke completo**

```powershell
uvicorn app.main:app --port 8000 &
curl http://localhost:8000/api/nfse/health
curl http://localhost:8000/api/health
```

Ambos respondem 200.

- [ ] **Step 3: Commit (se houver diff)**

```bash
git add backend/app/main.py
git commit -m "chore(nfse): wire routers em main.py" || echo "nada a commitar"
```

---

## Phase 5 — Worker GitHub Actions

### Task 18: `workers/nfse_scraper/selectors.py`

**Files:**
- Create: `backend/workers/__init__.py`
- Create: `backend/workers/nfse_scraper/__init__.py`
- Create: `backend/workers/nfse_scraper/selectors.py`

- [ ] **Step 1: Criar pacote**

`backend/workers/__init__.py` — vazio.
`backend/workers/nfse_scraper/__init__.py` — vazio.

- [ ] **Step 2: Criar `selectors.py`**

```python
# backend/workers/nfse_scraper/selectors.py
"""Seletores CSS/XPath p/ portal BHISS Digital.

CENTRALIZADO p/ facilitar manutenção quando portal muda.
Cada constante vem com comentário e timestamp de última validação.
"""
# Última validação: 2026-05-20

LOGIN_URL = "https://bhissdigital.pbh.gov.br/nfse/"

# Login form
SEL_LOGIN_USER = "input[name='usuario']"
SEL_LOGIN_PASS = "input[name='senha']"
SEL_LOGIN_SUBMIT = "button[type='submit'], input[type='submit']"
SEL_LOGIN_ERROR = ".mensagem-erro, .alert-danger"

# CAPTCHA
SEL_CAPTCHA_IMG = "img[alt*='captcha' i], #captcha img, .captcha img"

# Pós-login: identificar sucesso
SEL_DASHBOARD = "nav.menu-principal, #menu-nfse, a[href*='consultaNFSe']"

# Consulta NFS-e
SEL_MENU_CONSULTA = "a[href*='consultaNFSe'], a:has-text('Consultar')"
SEL_FILTRO_DATA_INI = "input[name*='dataInicio']"
SEL_FILTRO_DATA_FIM = "input[name*='dataFim']"
SEL_BTN_FILTRAR = "button:has-text('Filtrar'), input[value='Filtrar']"

# Exportação XML
SEL_BTN_EXPORTAR_XML = "a:has-text('Exportar XML'), button:has-text('XML')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/workers
git commit -m "feat(nfse-worker): seletores BHISS Digital centralizados"
```

---

### Task 19: `workers/nfse_scraper/client.py` (Playwright)

**Files:**
- Create: `backend/workers/nfse_scraper/client.py`

- [ ] **Step 1: Implementar cliente**

```python
# backend/workers/nfse_scraper/client.py
"""Cliente headless Playwright p/ portal BHISS Digital.

Fluxo:
1. login(login, senha)
2. fetch_nfse_periodo(data_inicio, data_fim) -> list[bytes XML]

Exceções:
- LoginError, CaptchaError, LayoutChangedError, PortalDownError.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import date
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    Page,
    TimeoutError as PWTimeout,
    async_playwright,
)

from . import selectors as S

log = logging.getLogger(__name__)


class ScraperError(Exception):
    pass


class LoginError(ScraperError):
    pass


class CaptchaError(ScraperError):
    pass


class LayoutChangedError(ScraperError):
    pass


class PortalDownError(ScraperError):
    pass


class BHISSClient:
    def __init__(self, screenshot_dir: Path | None = None) -> None:
        self.screenshot_dir = screenshot_dir or Path("screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._pw = None
        self._browser = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> "BHISSClient":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = await self._browser.new_context(
            user_agent="Mozilla/5.0 honorario-cf-nfse-sync",
            locale="pt-BR",
        )
        self._page = await ctx.new_page()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def _human_delay(self) -> None:
        await asyncio.sleep(random.uniform(0.8, 1.5))

    async def _shot(self, name: str) -> Path:
        p = self.screenshot_dir / f"{name}.png"
        if self._page:
            try:
                await self._page.screenshot(path=str(p), full_page=True)
            except Exception:
                pass
        return p

    async def login(self, login: str, senha: str) -> None:
        assert self._page
        try:
            await self._page.goto(S.LOGIN_URL, timeout=30_000)
        except PWTimeout as e:
            await self._shot("portal_down")
            raise PortalDownError(str(e)) from e

        if await self._page.locator(S.SEL_CAPTCHA_IMG).count() > 0:
            await self._shot("captcha_pre_login")
            raise CaptchaError("CAPTCHA presente na tela de login")

        try:
            await self._page.fill(S.SEL_LOGIN_USER, login)
            await self._human_delay()
            await self._page.fill(S.SEL_LOGIN_PASS, senha)
            await self._human_delay()
            await self._page.click(S.SEL_LOGIN_SUBMIT)
        except PWTimeout as e:
            await self._shot("login_form_layout")
            raise LayoutChangedError(f"form login: {e}") from e

        try:
            await self._page.wait_for_selector(S.SEL_DASHBOARD, timeout=20_000)
        except PWTimeout:
            err_count = await self._page.locator(S.SEL_LOGIN_ERROR).count()
            if err_count > 0:
                await self._shot("login_invalid")
                raise LoginError("login/senha inválidos")
            if await self._page.locator(S.SEL_CAPTCHA_IMG).count() > 0:
                await self._shot("captcha_post_login")
                raise CaptchaError("CAPTCHA após submit")
            await self._shot("login_no_dashboard")
            raise LayoutChangedError("dashboard não detectado após login")

    async def fetch_nfse_periodo(self, ini: date, fim: date) -> list[bytes]:
        assert self._page
        try:
            await self._page.click(S.SEL_MENU_CONSULTA)
            await self._human_delay()
            await self._page.fill(S.SEL_FILTRO_DATA_INI, ini.strftime("%d/%m/%Y"))
            await self._page.fill(S.SEL_FILTRO_DATA_FIM, fim.strftime("%d/%m/%Y"))
            await self._human_delay()
            await self._page.click(S.SEL_BTN_FILTRAR)
            await self._page.wait_for_load_state("networkidle", timeout=30_000)
        except PWTimeout as e:
            await self._shot("consulta_layout")
            raise LayoutChangedError(f"menu consulta: {e}") from e

        try:
            async with self._page.expect_download(timeout=60_000) as dl_info:
                await self._page.click(S.SEL_BTN_EXPORTAR_XML)
            dl = await dl_info.value
            path = await dl.path()
        except PWTimeout as e:
            await self._shot("export_xml")
            raise LayoutChangedError(f"exportar XML: {e}") from e

        if not path:
            return []

        data = Path(path).read_bytes()
        # PBH retorna lote ZIP ou XML único: detectar
        if data[:2] == b"PK":
            from zipfile import ZipFile
            from io import BytesIO

            xmls: list[bytes] = []
            with ZipFile(BytesIO(data)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".xml"):
                        xmls.append(zf.read(name))
            return xmls
        return [data]
```

- [ ] **Step 2: Smoke offline (sem rede)**

```powershell
cd backend
python -c "from workers.nfse_scraper.client import BHISSClient, LoginError; print('ok')"
```

Esperado: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/workers/nfse_scraper/client.py
git commit -m "feat(nfse-worker): BHISSClient Playwright (login, fetch_periodo, exceptions tipadas)"
```

---

### Task 20: `workers/nfse_scraper/run.py` (CLI entrypoint)

**Files:**
- Create: `backend/workers/nfse_scraper/run.py`

- [ ] **Step 1: Implementar CLI**

```python
# backend/workers/nfse_scraper/run.py
"""Entrypoint do worker NFS-e (GitHub Actions runner).

Uso:
    python -m backend.workers.nfse_scraper.run --cnpj 12345678000199
    python -m backend.workers.nfse_scraper.run --cnpj 12345678000199 --inicio 2026-05-01 --fim 2026-05-31
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

from .client import (
    BHISSClient,
    CaptchaError,
    LayoutChangedError,
    LoginError,
    PortalDownError,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nfse-worker")


async def _main(cnpj: str, inicio: date, fim: date, api_url: str, token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30) as http:
        # 1) buscar credencial
        r = await http.get(f"{api_url}/api/nfse/credenciais/{cnpj}", headers=headers)
        if r.status_code != 200:
            log.error("falha ao obter credencial: %s %s", r.status_code, r.text)
            await _report(http, api_url, token, cnpj, "erro_login",
                         motivo=f"credencial unreachable: {r.status_code}")
            return 2
        cred = r.json()

        screenshots = Path("screenshots")
        try:
            async with BHISSClient(screenshot_dir=screenshots) as client:
                await client.login(cred["login"], cred["senha"])
                xmls = await client.fetch_nfse_periodo(inicio, fim)
        except LoginError as e:
            await _report(http, api_url, token, cnpj, "erro_login", motivo=str(e))
            return 3
        except CaptchaError as e:
            await _report(http, api_url, token, cnpj, "captcha", motivo=str(e))
            return 4
        except LayoutChangedError as e:
            await _report(http, api_url, token, cnpj, "layout", motivo=str(e))
            return 5
        except PortalDownError as e:
            await _report(http, api_url, token, cnpj, "portal_down", motivo=str(e))
            return 6

        # 2) enviar XMLs
        payload = {
            "cnpj_prestador": cnpj,
            "periodo_inicio": inicio.isoformat(),
            "periodo_fim": fim.isoformat(),
            "origem": "cron",
            "disparado_por": os.getenv("GITHUB_TRIGGERING_ACTOR", "gh-actions"),
            "xmls_b64": [base64.b64encode(x).decode() for x in xmls],
        }
        r = await http.post(f"{api_url}/api/nfse/ingest", headers=headers, json=payload, timeout=120)
        if r.status_code >= 400:
            log.error("ingest falhou: %s %s", r.status_code, r.text)
            return 7
        log.info("ingest ok: %s", r.json())
        return 0


async def _report(http, api_url, token, cnpj, status, motivo):
    try:
        await http.post(
            f"{api_url}/api/nfse/sync-status",
            headers={"Authorization": f"Bearer {token}"},
            params={"cnpj_prestador": cnpj, "status": status, "motivo": motivo},
        )
    except Exception as e:
        log.error("falha ao reportar status: %s", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cnpj", required=True)
    ap.add_argument("--inicio", help="YYYY-MM-DD (default: ontem)")
    ap.add_argument("--fim", help="YYYY-MM-DD (default: hoje)")
    args = ap.parse_args()

    api_url = os.environ["HONORARIO_API_URL"].rstrip("/")
    token = os.environ["NFSE_WORKER_TOKEN"]

    fim = date.fromisoformat(args.fim) if args.fim else date.today()
    inicio = date.fromisoformat(args.inicio) if args.inicio else (fim - timedelta(days=1))

    code = asyncio.run(_main(args.cnpj, inicio, fim, api_url, token))
    sys.exit(code)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke (sem rede, deve imprimir help)**

```powershell
cd backend
python -m workers.nfse_scraper.run --help
```

Esperado: usage / help.

- [ ] **Step 3: Commit**

```bash
git add backend/workers/nfse_scraper/run.py
git commit -m "feat(nfse-worker): CLI run.py (fetch credencial -> scrape -> POST /ingest)"
```

---

### Task 21: `workers/nfse_scraper/requirements.txt`

**Files:**
- Create: `backend/workers/nfse_scraper/requirements.txt`

- [ ] **Step 1: Criar requirements isolado**

```
# backend/workers/nfse_scraper/requirements.txt
playwright==1.49.0
httpx==0.27.2
```

- [ ] **Step 2: Commit**

```bash
git add backend/workers/nfse_scraper/requirements.txt
git commit -m "chore(nfse-worker): requirements isolados (playwright, httpx)"
```

---

### Task 22: GitHub Actions workflow `nfse-sync.yml`

**Files:**
- Create: `.github/workflows/nfse-sync.yml` (raiz do repo Codigo, NÃO no Honorario-cf submodule)

> **Nota:** GH Actions detecta workflows na raiz do repositório. Confirme se `Honorario-cf` é submodule do repo principal `Codigo` — se sim, este arquivo vai em `Codigo/.github/workflows/`. Se `Honorario-cf` tem seu próprio repo GitHub, vai em `Honorario-cf/.github/workflows/`. Assumimos o último.

- [ ] **Step 1: Criar workflow**

Caminho: `Honorario-cf/.github/workflows/nfse-sync.yml`.

```yaml
name: nfse-sync

on:
  schedule:
    - cron: '0 6 * * *'      # 03:00 America/Sao_Paulo
  workflow_dispatch:
    inputs:
      periodo_inicio:
        description: 'YYYY-MM-DD (opcional)'
        required: false
      periodo_fim:
        description: 'YYYY-MM-DD (opcional)'
        required: false

concurrency:
  group: nfse-sync-${{ github.ref }}
  cancel-in-progress: false

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        cnpj: ${{ fromJSON(vars.PRESTADORES_CNPJS || '[]') }}
    env:
      HONORARIO_API_URL: ${{ secrets.HONORARIO_API_URL }}
      NFSE_WORKER_TOKEN: ${{ secrets.NFSE_WORKER_TOKEN }}
    steps:
      - uses: actions/checkout@v4

      - name: Check feature flag
        run: |
          STATUS=$(curl -fsS "$HONORARIO_API_URL/api/nfse/health" || echo '{"enabled":false}')
          ENABLED=$(echo "$STATUS" | python -c "import sys,json; print(json.load(sys.stdin).get('enabled', False))")
          if [ "$ENABLED" != "True" ]; then
            echo "NFS-e desabilitado, encerrando."
            exit 0
          fi

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: 'backend/workers/nfse_scraper/requirements.txt'

      - run: pip install -r backend/workers/nfse_scraper/requirements.txt
      - run: python -m playwright install --with-deps chromium

      - name: Run scraper
        working-directory: backend
        run: |
          ARGS="--cnpj ${{ matrix.cnpj }}"
          if [ -n "${{ github.event.inputs.periodo_inicio }}" ]; then
            ARGS="$ARGS --inicio ${{ github.event.inputs.periodo_inicio }}"
          fi
          if [ -n "${{ github.event.inputs.periodo_fim }}" ]; then
            ARGS="$ARGS --fim ${{ github.event.inputs.periodo_fim }}"
          fi
          python -m workers.nfse_scraper.run $ARGS

      - name: Upload screenshots on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: screenshots-${{ matrix.cnpj }}
          path: backend/screenshots/
          retention-days: 7
```

- [ ] **Step 2: Documentar setup necessário**

Criar `Honorario-cf/docs/runbooks/nfse-gh-actions-setup.md`:

```markdown
# Setup GitHub Actions p/ nfse-sync

## Secrets necessários (repo Settings → Secrets → Actions)

- `HONORARIO_API_URL` — URL do backend Render (sem barra final), ex.: `https://honorario-cf-api.onrender.com`
- `NFSE_WORKER_TOKEN` — mesmo valor da env `NFSE_WORKER_TOKEN` no Render

## Variables (repo Settings → Variables → Actions)

- `PRESTADORES_CNPJS` — JSON array dos CNPJs, ex.: `["12345678000199"]`

## Verificação

- Manual: Actions → nfse-sync → Run workflow.
- Verificar logs do job (1 por CNPJ).
- Em falha, artifacts `screenshots-<cnpj>` ficam disponíveis 7 dias.
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/nfse-sync.yml docs/runbooks/nfse-gh-actions-setup.md
git commit -m "feat(nfse-worker): GH Actions workflow nfse-sync (cron diário + manual)"
```

---

### Task 23: GH Actions integration workflow (homologação opcional)

**Files:**
- Create: `Honorario-cf/.github/workflows/nfse-integration.yml`

- [ ] **Step 1: Criar workflow integration**

```yaml
name: nfse-integration

on:
  schedule:
    - cron: '0 4 * * *'   # 01:00 SP — antes do sync diário
  workflow_dispatch:

jobs:
  integration:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      PBH_TEST_USER: ${{ secrets.PBH_TEST_USER }}
      PBH_TEST_PASS: ${{ secrets.PBH_TEST_PASS }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r backend/requirements.txt -r backend/workers/nfse_scraper/requirements.txt
      - run: python -m playwright install --with-deps chromium
      - name: Run integration tests
        working-directory: backend
        run: |
          if [ -z "$PBH_TEST_USER" ]; then
            echo "PBH_TEST_USER ausente, pulando."
            exit 0
          fi
          pytest tests/integration/ -m integration -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/nfse-integration.yml
git commit -m "ci(nfse): workflow integration noturno contra portal PBH (opt-in via secrets)"
```

---

## Phase 6 — Frontend

### Task 24: `frontend/src/app/lib/nfse-api.ts` (cliente)

**Files:**
- Create: `frontend/src/app/lib/nfse-api.ts`

- [ ] **Step 1: Criar cliente**

```typescript
// frontend/src/app/lib/nfse-api.ts
import { getAuthHeaders } from "./api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

export type NFSeStatus =
  | "auto" | "manual" | "pendente" | "sem_match" | "erro" | "cancelada";

export interface NFSeOut {
  id: number;
  cnpj_prestador: string;
  numero: string;
  serie: string | null;
  competencia: string;
  data_emissao: string;
  tomador_doc: string;
  tomador_nome: string | null;
  valor_servicos: string;
  valor_liquido: string;
  cancelada: boolean;
  status_matching: NFSeStatus;
  contract_id: string | null;
  participacao_id: number | null;
  pagamento_id: number | null;
  motivo: string | null;
}

export interface HealthResponse {
  enabled: boolean;
  last_job?: {
    iniciado_em: string | null;
    finalizado_em: string | null;
    status: string;
    total_nfs: number;
    erros: number;
  } | null;
  now?: string;
}

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...getAuthHeaders(), "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const nfseApi = {
  health: () => _fetch<HealthResponse>("/api/nfse/health"),

  listar: (params: { cnpj_prestador?: string; competencia_mes?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params.cnpj_prestador) q.set("cnpj_prestador", params.cnpj_prestador);
    if (params.competencia_mes) q.set("competencia_mes", params.competencia_mes);
    if (params.status) q.set("status", params.status);
    return _fetch<NFSeOut[]>(`/api/nfse?${q.toString()}`);
  },

  vincular: (nfse_id: number, body: { contract_id: string; motivo?: string }) =>
    _fetch<NFSeOut>(`/api/nfse/${nfse_id}/vincular`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  syncManual: (cnpj_prestador: string) =>
    _fetch<{ ok: boolean; msg: string }>(`/api/nfse/sync?cnpj_prestador=${cnpj_prestador}`, {
      method: "POST",
    }),
};

export interface CredencialPbhOut {
  id: number;
  cnpj_prestador: string;
  ativo: boolean;
  criado_em: string;
  criado_por: string;
  motivo_inativacao: string | null;
}

export const credencialApi = {
  listar: () => _fetch<CredencialPbhOut[]>("/api/admin/credencial-pbh"),
  upsert: (body: { cnpj_prestador: string; login: string; senha: string }) =>
    _fetch<CredencialPbhOut>("/api/admin/credencial-pbh", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  desativar: (cnpj: string, motivo?: string) => {
    const q = new URLSearchParams();
    if (motivo) q.set("motivo", motivo);
    return _fetch<CredencialPbhOut>(
      `/api/admin/credencial-pbh/${cnpj}/desativar?${q.toString()}`,
      { method: "POST" }
    );
  },
};
```

- [ ] **Step 2: Smoke (tsc)**

```powershell
cd frontend
npx tsc --noEmit
```

Esperado: sem erros relacionados a `nfse-api.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/lib/nfse-api.ts
git commit -m "feat(nfse-ui): cliente API (health, listar, vincular, sync, credencial)"
```

---

### Task 25: Componentes `HealthBanner` e `SyncButton`

**Files:**
- Create: `frontend/src/components/nfse/HealthBanner.tsx`
- Create: `frontend/src/components/nfse/SyncButton.tsx`

- [ ] **Step 1: HealthBanner**

```tsx
// frontend/src/components/nfse/HealthBanner.tsx
"use client";

import { useEffect, useState } from "react";
import { nfseApi, type HealthResponse } from "@/app/lib/nfse-api";

export function HealthBanner() {
  const [h, setH] = useState<HealthResponse | null>(null);

  useEffect(() => {
    nfseApi.health().then(setH).catch(() => setH({ enabled: false }));
  }, []);

  if (!h || !h.enabled) return null;
  const last = h.last_job;
  if (!last) return null;

  const stale = last.finalizado_em
    ? Date.now() - new Date(last.finalizado_em).getTime() > 36 * 3600 * 1000
    : true;
  const ok = last.status === "ok" && !stale;
  if (ok) return null;

  return (
    <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <strong>NFS-e sync:</strong>{" "}
      {last.status !== "ok"
        ? `último job falhou (${last.status})`
        : "sem sync há mais de 36h"}
      {last.iniciado_em && ` — ${new Date(last.iniciado_em).toLocaleString("pt-BR")}`}
    </div>
  );
}
```

- [ ] **Step 2: SyncButton**

```tsx
// frontend/src/components/nfse/SyncButton.tsx
"use client";

import { useState } from "react";
import { nfseApi } from "@/app/lib/nfse-api";

export function SyncButton({ cnpj }: { cnpj: string }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={async () => {
          setLoading(true);
          setMsg("");
          try {
            const r = await nfseApi.syncManual(cnpj);
            setMsg(r.msg);
          } catch (e) {
            setMsg(e instanceof Error ? e.message : "erro");
          } finally {
            setLoading(false);
          }
        }}
        disabled={loading || !cnpj}
        className="px-3 py-1.5 text-xs bg-primary-dark text-white rounded font-medium disabled:opacity-50"
      >
        {loading ? "Agendando..." : "Sincronizar agora"}
      </button>
      {msg && <span className="text-xs text-muted">{msg}</span>}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/nfse/HealthBanner.tsx frontend/src/components/nfse/SyncButton.tsx
git commit -m "feat(nfse-ui): HealthBanner + SyncButton"
```

---

### Task 26: `NotasFiscaisLista` + `VincularModal`

**Files:**
- Create: `frontend/src/components/nfse/NotasFiscaisLista.tsx`
- Create: `frontend/src/components/nfse/VincularModal.tsx`

- [ ] **Step 1: NotasFiscaisLista**

```tsx
// frontend/src/components/nfse/NotasFiscaisLista.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { nfseApi, type NFSeOut } from "@/app/lib/nfse-api";
import { VincularModal } from "./VincularModal";

function brl(v: string) {
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const statusBadge: Record<NFSeOut["status_matching"], { label: string; cls: string }> = {
  auto: { label: "✓ auto", cls: "bg-green-100 text-green-800" },
  manual: { label: "✓ manual", cls: "bg-green-100 text-green-800" },
  pendente: { label: "⚠ pendente", cls: "bg-amber-100 text-amber-800" },
  sem_match: { label: "✗ sem match", cls: "bg-red-100 text-red-800" },
  erro: { label: "✗ erro", cls: "bg-red-100 text-red-800" },
  cancelada: { label: "🚫 cancelada", cls: "bg-gray-200 text-gray-700" },
};

export function NotasFiscaisLista({ competencia_mes }: { competencia_mes: string }) {
  const [items, setItems] = useState<NFSeOut[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [editing, setEditing] = useState<NFSeOut | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    nfseApi
      .listar({ competencia_mes, status: statusFilter || undefined })
      .then(setItems)
      .finally(() => setLoading(false));
  }, [competencia_mes, statusFilter]);

  useEffect(() => { refresh(); }, [refresh]);

  const resumo = useMemo(() => {
    const counts: Record<string, number> = {};
    items.forEach((n) => { counts[n.status_matching] = (counts[n.status_matching] || 0) + 1; });
    return counts;
  }, [items]);

  if (loading) return <div className="text-muted p-6">Carregando NFs...</div>;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-xs">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-border rounded px-2 py-1"
        >
          <option value="">Todos status</option>
          <option value="auto">Auto</option>
          <option value="manual">Manual</option>
          <option value="pendente">Pendente</option>
          <option value="sem_match">Sem match</option>
          <option value="cancelada">Cancelada</option>
        </select>
        <span className="text-muted">
          Resumo:{" "}
          {(["auto","manual","pendente","sem_match","cancelada"] as const)
            .map((k) => `${resumo[k] || 0} ${k}`)
            .join(" · ")}
        </span>
      </div>

      {items.length === 0 ? (
        <div className="text-muted p-6 text-center border border-dashed border-border rounded-lg">
          Nenhuma NF nesta competência.
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-xs text-muted border-b border-border">
            <tr>
              <th className="text-left py-2">Nº</th>
              <th className="text-left py-2">Tomador</th>
              <th className="text-right py-2">Valor</th>
              <th className="text-right py-2">Líquido</th>
              <th className="text-left py-2">Status</th>
              <th className="text-left py-2">Contrato</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((n) => {
              const b = statusBadge[n.status_matching] ?? statusBadge.erro;
              return (
                <tr key={n.id} className="border-b border-border/40">
                  <td className="py-2 font-mono text-xs">{n.numero}</td>
                  <td className="py-2">
                    {n.tomador_nome || "—"}{" "}
                    <span className="text-xs text-muted">{n.tomador_doc}</span>
                  </td>
                  <td className="py-2 text-right">{brl(n.valor_servicos)}</td>
                  <td className="py-2 text-right">{brl(n.valor_liquido)}</td>
                  <td className="py-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${b.cls}`}>{b.label}</span>
                  </td>
                  <td className="py-2 text-xs">{n.contract_id?.slice(0, 8) || "—"}</td>
                  <td className="py-2 text-right">
                    {(n.status_matching === "pendente" || n.status_matching === "sem_match") && (
                      <button
                        onClick={() => setEditing(n)}
                        className="px-2 py-1 text-xs bg-primary-dark text-white rounded hover:opacity-90"
                      >
                        Vincular
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {editing && (
        <VincularModal
          nfse={editing}
          onClose={() => setEditing(null)}
          onDone={() => { setEditing(null); refresh(); }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: VincularModal**

```tsx
// frontend/src/components/nfse/VincularModal.tsx
"use client";

import { useState } from "react";
import { nfseApi, type NFSeOut } from "@/app/lib/nfse-api";

export function VincularModal({
  nfse, onClose, onDone,
}: { nfse: NFSeOut; onClose: () => void; onDone: () => void }) {
  const [contractId, setContractId] = useState("");
  const [motivo, setMotivo] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      await nfseApi.vincular(nfse.id, { contract_id: contractId, motivo: motivo || undefined });
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "erro");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <form onSubmit={submit}
            className="bg-card border border-border rounded-lg p-6 max-w-md w-full space-y-3 text-sm">
        <div className="flex justify-between items-center">
          <h3 className="font-medium">Vincular NF #{nfse.numero}</h3>
          <button type="button" onClick={onClose} className="text-muted">✕</button>
        </div>
        <p className="text-xs text-muted">
          Tomador: {nfse.tomador_nome} ({nfse.tomador_doc}) — competência {nfse.competencia}
        </p>
        <label className="block">
          <span className="text-xs text-muted">ID do contrato *</span>
          <input
            required value={contractId}
            onChange={(e) => setContractId(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded"
          />
        </label>
        <label className="block">
          <span className="text-xs text-muted">Motivo</span>
          <input
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded"
          />
        </label>
        {err && <div className="text-xs text-red-700">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose}
                  className="px-3 py-1.5 border border-border rounded text-xs">Cancelar</button>
          <button type="submit" disabled={saving}
                  className="px-3 py-1.5 bg-primary-dark text-white rounded text-xs disabled:opacity-50">
            {saving ? "Vinculando..." : "Confirmar"}
          </button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/nfse
git commit -m "feat(nfse-ui): NotasFiscaisLista + VincularModal"
```

---

### Task 27: Adicionar aba "Notas Fiscais" em `/financeiro`

**Files:**
- Modify: `frontend/src/app/financeiro/page.tsx`

- [ ] **Step 1: Editar tipos de aba**

Em `frontend/src/app/financeiro/page.tsx`, localizar:

```ts
const [tab, setTab] = useState<"pendentes" | "lista" | "nova" | "simular">("pendentes");
```

Trocar por:

```ts
const [tab, setTab] = useState<"pendentes" | "lista" | "nova" | "simular" | "nfse">("pendentes");
```

E na `nav` (procurar `(["pendentes", "lista", "nova", "simular"] as const).map`):

```tsx
(["pendentes", "lista", "nova", "simular", "nfse"] as const).map((t) => (
  ...
  {t === "nfse" && "Notas Fiscais"}
```

Adicionar bloco de renderização logo após `{tab === "simular" && <Simulador />}`:

```tsx
{tab === "nfse" && <AbaNotasFiscais />}
```

E no topo do arquivo importar:

```tsx
import { HealthBanner } from "@/components/nfse/HealthBanner";
import { NotasFiscaisLista } from "@/components/nfse/NotasFiscaisLista";
import { SyncButton } from "@/components/nfse/SyncButton";
```

Adicionar ao final do arquivo:

```tsx
function AbaNotasFiscais() {
  const now = new Date();
  const defaultMes = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [mes, setMes] = useState(defaultMes);
  const [cnpj, setCnpj] = useState("");

  return (
    <div className="space-y-4">
      <HealthBanner />
      <div className="flex items-end gap-3">
        <label className="block text-xs">
          <span className="block text-muted mb-1">Competência</span>
          <input
            type="month"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="px-2 py-1 border border-border rounded"
          />
        </label>
        <label className="block text-xs">
          <span className="block text-muted mb-1">CNPJ prestador</span>
          <input
            value={cnpj}
            onChange={(e) => setCnpj(e.target.value)}
            placeholder="só dígitos"
            className="px-2 py-1 border border-border rounded font-mono"
          />
        </label>
        <SyncButton cnpj={cnpj} />
      </div>
      <NotasFiscaisLista competencia_mes={mes} />
    </div>
  );
}
```

- [ ] **Step 2: Smoke**

```powershell
cd frontend
npm run dev
```

Abrir `http://localhost:3000/financeiro` logado como financeiro — aba "Notas Fiscais" aparece.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/financeiro/page.tsx
git commit -m "feat(nfse-ui): aba Notas Fiscais em /financeiro"
```

---

### Task 28: Tela admin `/admin/credenciais-pbh`

**Files:**
- Create: `frontend/src/app/admin/credenciais-pbh/page.tsx`
- Create: `frontend/src/components/admin/CredencialPbhForm.tsx`

- [ ] **Step 1: Component form**

```tsx
// frontend/src/components/admin/CredencialPbhForm.tsx
"use client";

import { useEffect, useState } from "react";
import { credencialApi, type CredencialPbhOut } from "@/app/lib/nfse-api";

export function CredencialPbhPanel() {
  const [items, setItems] = useState<CredencialPbhOut[]>([]);
  const [form, setForm] = useState({ cnpj_prestador: "", login: "", senha: "" });
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = () => credencialApi.listar().then(setItems).catch((e) => setErr(String(e)));
  useEffect(() => { refresh(); }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setErr("");
    try {
      await credencialApi.upsert(form);
      setForm({ cnpj_prestador: "", login: "", senha: "" });
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "erro");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="bg-card border border-border rounded-lg p-4 space-y-3 text-sm">
        <h3 className="font-medium">Nova / atualizar credencial</h3>
        <div className="grid md:grid-cols-3 gap-3">
          <label>
            <span className="block text-xs text-muted">CNPJ prestador (só dígitos)</span>
            <input required value={form.cnpj_prestador}
                   onChange={(e) => setForm({ ...form, cnpj_prestador: e.target.value })}
                   className="w-full px-2 py-1 border border-border rounded font-mono"/>
          </label>
          <label>
            <span className="block text-xs text-muted">Login BHISS</span>
            <input required value={form.login}
                   onChange={(e) => setForm({ ...form, login: e.target.value })}
                   className="w-full px-2 py-1 border border-border rounded"/>
          </label>
          <label>
            <span className="block text-xs text-muted">Senha</span>
            <input required type="password" value={form.senha}
                   onChange={(e) => setForm({ ...form, senha: e.target.value })}
                   className="w-full px-2 py-1 border border-border rounded"/>
          </label>
        </div>
        {err && <div className="text-xs text-red-700">{err}</div>}
        <button disabled={saving}
                className="px-3 py-1.5 bg-primary-dark text-white rounded text-xs disabled:opacity-50">
          {saving ? "Salvando..." : "Salvar credencial"}
        </button>
        <p className="text-xs text-muted">
          Senha é criptografada em repouso (AES-GCM). Nunca aparece em logs ou listagens.
        </p>
      </form>

      <div className="space-y-2">
        <h3 className="font-medium text-sm">Credenciais ativas</h3>
        {items.length === 0 ? (
          <p className="text-xs text-muted">Nenhuma credencial cadastrada.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs text-muted border-b border-border">
              <tr>
                <th className="text-left py-2">CNPJ</th>
                <th className="text-left py-2">Status</th>
                <th className="text-left py-2">Cadastrado por</th>
                <th className="text-left py-2">Em</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-b border-border/40">
                  <td className="py-2 font-mono text-xs">{c.cnpj_prestador}</td>
                  <td className="py-2">
                    <span className={c.ativo
                        ? "text-green-700 text-xs"
                        : "text-red-700 text-xs"}>
                      {c.ativo ? "ativo" : `inativo${c.motivo_inativacao ? " · " + c.motivo_inativacao : ""}`}
                    </span>
                  </td>
                  <td className="py-2 text-xs">{c.criado_por}</td>
                  <td className="py-2 text-xs">{new Date(c.criado_em).toLocaleString("pt-BR")}</td>
                  <td className="py-2 text-right">
                    {c.ativo && (
                      <button
                        onClick={async () => {
                          if (!confirm("Desativar credencial?")) return;
                          await credencialApi.desativar(c.cnpj_prestador, "manual");
                          refresh();
                        }}
                        className="text-xs text-red-700 hover:underline"
                      >
                        Desativar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Página**

```tsx
// frontend/src/app/admin/credenciais-pbh/page.tsx
"use client";

import { CredencialPbhPanel } from "@/components/admin/CredencialPbhForm";

export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide">
          Credenciais PBH — BHISS Digital
        </h1>
        <p className="text-sm text-muted mt-1">
          Cadastro de login/senha do portal usados pelo worker NFS-e.
        </p>
      </header>
      <CredencialPbhPanel />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/admin/credenciais-pbh frontend/src/components/admin/CredencialPbhForm.tsx
git commit -m "feat(nfse-ui): tela admin /admin/credenciais-pbh"
```

---

## Phase 7 — Ops & Verification

### Task 29: Script `rotate_kek.py` + runbook

**Files:**
- Create: `backend/scripts/rotate_kek.py`
- Create: `Honorario-cf/docs/runbooks/rotate-kek.md`

- [ ] **Step 1: Script**

```python
# backend/scripts/rotate_kek.py
"""Rotaciona NFSE_KEK: decifra com OLD_KEK e re-cifra com NEW_KEK.

Uso:
  set OLD_KEK=<base64 atual>
  set NEW_KEK=<base64 novo>
  python -m backend.scripts.rotate_kek

Após sucesso, atualize a env NFSE_KEK no Render com NEW_KEK e remova OLD_KEK.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from app.database import SessionLocal
from app.services.crypto import CryptoBox, EncryptedBlob, InvalidCipherError


def main() -> int:
    old = os.environ.get("OLD_KEK")
    new = os.environ.get("NEW_KEK")
    if not old or not new:
        print("Defina OLD_KEK e NEW_KEK", file=sys.stderr)
        return 1
    if old == new:
        print("OLD_KEK == NEW_KEK; nada a fazer", file=sys.stderr)
        return 1

    src = CryptoBox(old)
    dst = CryptoBox(new)
    with SessionLocal() as db:
        rows = db.execute(
            text("""SELECT id, login_enc, nonce_login, senha_enc, nonce_senha
                    FROM credencial_pbh""")
        ).fetchall()
        for row in rows:
            cid, le, nl, se, ns = row
            try:
                login = src.decrypt(EncryptedBlob(nonce=nl, ciphertext=le))
                senha = src.decrypt(EncryptedBlob(nonce=ns, ciphertext=se))
            except InvalidCipherError as e:
                print(f"FALHA decrypt id={cid}: {e}", file=sys.stderr)
                return 2
            le2 = dst.encrypt(login)
            se2 = dst.encrypt(senha)
            db.execute(
                text("""UPDATE credencial_pbh
                        SET login_enc=:le, nonce_login=:nl,
                            senha_enc=:se, nonce_senha=:ns,
                            atualizado_em=:n
                        WHERE id=:id"""),
                {"le": le2.ciphertext, "nl": le2.nonce,
                 "se": se2.ciphertext, "ns": se2.nonce,
                 "n": datetime.now(timezone.utc), "id": cid},
            )
        db.commit()
    print(f"OK: {len(rows)} credenciais re-cifradas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Runbook**

```markdown
<!-- Honorario-cf/docs/runbooks/rotate-kek.md -->
# Rotacionar NFSE_KEK

## Quando rotacionar

- Suspeita de vazamento (commit acidental, dump do banco em mãos erradas, ex-colaborador com acesso a env).
- Política trimestral preventiva.

## Pré-requisitos

- Acesso ao Render dashboard.
- KEK atual em mãos (será necessário como `OLD_KEK`).
- Banco em quiesce (poucos writes simultâneos) ou janela de manutenção.

## Procedimento

1. Gere novo KEK:
   ```powershell
   python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
   ```
2. Conecte ao container/servidor com `OLD_KEK` (NFSE_KEK atual) e `NEW_KEK` definidos:
   ```powershell
   $env:OLD_KEK = "<atual>"
   $env:NEW_KEK = "<novo>"
   python -m backend.scripts.rotate_kek
   ```
3. Após `OK: N credenciais re-cifradas.`, troque `NFSE_KEK` no Render para o NOVO valor e redeploy.
4. Smoke: `GET /api/nfse/credenciais/<cnpj>` com worker token deve retornar login/senha corretamente.
5. Apague variável temporária `OLD_KEK` do ambiente onde rotacionou.
6. Anote no audit log da empresa.

## Rollback

Se o passo 4 falhar, troque `NFSE_KEK` de volta para o valor antigo e investigue.
```

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/rotate_kek.py docs/runbooks/rotate-kek.md
git commit -m "ops(nfse): script rotate_kek + runbook"
```

---

### Task 30: Smoke checklist E2E

**Files:**
- Create: `Honorario-cf/docs/qa/nfse-smoke.md`

- [ ] **Step 1: Documento**

```markdown
<!-- Honorario-cf/docs/qa/nfse-smoke.md -->
# Smoke E2E — NFS-e BH

Executar antes de habilitar `NFSE_ENABLED=true` em produção.

## Pré-requisitos

- Migrations 0001 e 0002 aplicadas.
- `NFSE_KEK`, `NFSE_WORKER_TOKEN`, `HONORARIO_API_URL` configurados.
- GH Actions secrets `HONORARIO_API_URL`, `NFSE_WORKER_TOKEN` + var `PRESTADORES_CNPJS` definidos.
- Credencial homolog PBH em mãos (ou produção se já em piloto).

## Roteiro

1. **Cadastrar credencial**
   - Login no honorario-cf como `admin`.
   - Acessar `/admin/credenciais-pbh`.
   - Preencher CNPJ + login + senha → "Salvar credencial".
   - Esperado: linha aparece em "Credenciais ativas" como **ativo**.

2. **Disparar sync via GH Actions**
   - GitHub → Actions → `nfse-sync` → "Run workflow".
   - Preencher `periodo_inicio` / `periodo_fim` se desejar.
   - Esperado: job verde com logs `ingest ok: ...`.

3. **Conferir lista de NFs no frontend**
   - `/financeiro` → aba "Notas Fiscais" → competência do mês de teste.
   - Esperado: ≥1 NF listada com status válido.

4. **Vinculação automática**
   - Ao menos 1 NF deve aparecer com badge **✓ auto** e `Contrato#...` populado.
   - Conferir na aba "Participações" do mesmo contrato: novo pagamento listado com valor líquido correto.

5. **Vinculação manual**
   - Encontrar NF com status **⚠ pendente** ou **✗ sem match**.
   - Clicar "Vincular" → digitar contract_id válido → "Confirmar".
   - Esperado: badge muda para **✓ manual**, pagamento aparece em Participações.

6. **Cancelamento**
   - Cancelar uma NF no portal BHISS (homolog).
   - Aguardar próximo sync OU disparar manual.
   - Esperado: NF na lista muda para **🚫 cancelada**; pagamento original PERMANECE (não revertido); alerta no banner.

7. **Credencial inválida**
   - Em `/admin/credenciais-pbh`, alterar a senha p/ valor errado.
   - Disparar sync manual.
   - Esperado: workflow conclui (não falha vermelho); credencial fica **inativo** com motivo `login_invalido`; banner vermelho aparece em /financeiro.

8. **Audit log**
   - Conferir tabela `nfse_audit_log` no DB. Esperado: entradas para `credencial.upsert`, `nfse.vincular_manual`, `sync.start`/`sync.end`.

## Critérios de aceite

- [ ] Itens 1-8 completados sem erro inesperado.
- [ ] Suíte unit verde.
- [ ] Suíte integration verde contra homolog.
- [ ] Pelo menos 1 NF auto-vinculada gerou pagamento na Participação com o valor correto.
- [ ] KEK rotation runbook executado em dev sem perda de credenciais.
```

- [ ] **Step 2: Commit**

```bash
git add docs/qa/nfse-smoke.md
git commit -m "docs(nfse): smoke checklist E2E"
```

---

### Task 31: Verification final

**Files:**
- (nenhum — task de execução)

- [ ] **Step 1: Suíte completa**

```powershell
cd backend
.venv\Scripts\activate
pytest tests/ -v --ignore=tests/integration
```

Esperado: todos os testes unit verdes. Falha = parar e corrigir antes de prosseguir.

- [ ] **Step 2: Type/lint frontend**

```powershell
cd frontend
npx tsc --noEmit
npm run lint
```

Esperado: sem erros novos.

- [ ] **Step 3: Smoke local backend + frontend**

```powershell
# Terminal 1
cd backend
$env:NFSE_ENABLED="true"
$env:NFSE_KEK=$(python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())")
$env:NFSE_WORKER_TOKEN="dev-token"
uvicorn app.main:app --port 8000

# Terminal 2
cd frontend
npm run dev
```

Em `http://localhost:3000/financeiro` → aba Notas Fiscais aparece (vazia).
Em `http://localhost:3000/admin/credenciais-pbh` → form aparece p/ admin.
`http://localhost:8000/api/nfse/health` → `{"enabled": true, "last_job": null, ...}`.

- [ ] **Step 4: Executar smoke E2E** documentado em `docs/qa/nfse-smoke.md`.

- [ ] **Step 5: Confirmar gate de verificação**

Antes de mergear/habilitar em prod:

- [ ] Unit tests passando.
- [ ] Integration tests (opt-in) executados pelo menos uma vez com sucesso.
- [ ] Smoke E2E completo conforme `docs/qa/nfse-smoke.md`.
- [ ] Audit log conferido.
- [ ] KEK rotation runbook testado em dev.

- [ ] **Step 6: Commit final (se houver ajustes pós-verificação)**

```bash
git add -A
git commit -m "feat(nfse): finalização sprint NFS-e BH (ready para enable=true)" || echo "nada a commitar"
```

---

## Self-Review (executado durante a escrita)

### Spec coverage
- §1 Objetivo (registrar pagamento, calcular base participação, relatório) — Tasks 9–11, 16, 26. ✓
- §2 Abordagem (scraping Playwright + GH Actions) — Tasks 18–22. ✓
- §3 Arquitetura — distribuída entre Phase 1–6. ✓
- §4 Modelo de dados — Tasks 4–7. ✓
- §5 Fluxo de execução — Tasks 11–12, 15, 20. ✓
- §6 Matcher — Task 9. ✓
- §7 Tratamento de erros — Task 11 (parse error), 12 (lock), 15 (sync-status), 19 (exceções tipadas). ✓
- §8 Segurança — Tasks 3 (cripto), 14 (admin role), 15 (worker token), 29 (rotation). ✓
- §9 Timezone — implícito (datas em America/Sao_Paulo nos models; cron `0 6 * * *` UTC = 03:00 SP). ✓
- §10 UI — Tasks 24–28. ✓
- §11 Testes — Tasks 3, 8, 9, 10, 11, 12, 23. ✓
- §12 Deploy — Tasks 4 (Alembic), 17 (flag), 22 (workflow). ✓
- §13 Verification gate — Task 31. ✓
- §14 Fora de escopo — respeitado. ✓
- §15 Riscos — mitigados via tratamento de erros e runbook. ✓
- §16 Decisões — todas integradas. ✓

### Placeholder scan
- Sem "TBD", "TODO" em código de tarefas.
- Único "TODO" preservado é o existente em `database.py` original (não introduzido pelo plano).

### Type consistency
- `NFSeData`, `MatchResult`, `JobOutcome`, `PagamentoResult`, `CryptoBox`, `EncryptedBlob` — assinaturas conferidas entre tasks.
- `match_nfse`, `gerar_pagamento_para_nfse`, `ingest_payload`, `parse_nfse_xml` — assinaturas consistentes.
- `JobLockError` definido em Task 12 e usado em Task 15. ✓

### Gaps detectados durante review
- Spec menciona "endpoint `/api/nfse/sync` (financeiro/admin — opcional manual)"; Task 16 implementa como "agendar" (sem dispatch real de GH Actions API). Isso é uma simplificação consciente para o sprint atual: o usuário pode acionar manualmente via GH Actions UI. Integração programática com `gh api workflow-runs/dispatches` fica para iteração futura.
