# Financeiro SAP-like Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar `TaxCodeDB` (master data editável) + 6 colunas SAP-like em `participacao_pagamentos` + enums `TipoCobranca`/`NaturezaPagamento`/`TipoDocumento` + CRUD admin financeiro + atualizações frontend.

**Architecture:** Migration 0005 cria `tax_codes` (seed `PADRAO_1545`) e expande `participacao_pagamentos`. Cálculo passa a partir de `valor_bruto` (igual planilha): bruto → imposto (alíquota tax_code) → líquido → split contratual/sucumbencial → participação. Enums em constants Python validados por endpoint. Frontend ganha aba **Impostos** + `FormPagamento` com selects.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic 1.13, Pydantic v2, Next.js 15, TypeScript, Tailwind. Tests com pytest.

**Spec:** `docs/superpowers/specs/2026-05-22-financeiro-sap-like-design.md`

**Conventions:**
- Paths relativos à raiz do submodule `Honorario-cf/`
- Banco: SQLite local (`backend/honorarios.db`), Postgres prod (Render)
- Cwd backend para comandos Python; cwd frontend para npm

---

## Phase 1 — Backend Data Layer

### Task 1: Pydantic schemas TaxCode

**Files:**
- Create: `backend/app/models/tax_code.py`

- [ ] **Step 1: Criar schemas Pydantic**

```python
"""Schemas Pydantic para TaxCode (alíquotas fiscais agregadas)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TaxCodeBase(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=32)
    descricao: str = Field(..., min_length=1, max_length=256)
    aliquota_total: float = Field(..., ge=0, le=1)
    aliquota_iss: float = Field(0, ge=0, le=1)
    aliquota_pis: float = Field(0, ge=0, le=1)
    aliquota_cofins: float = Field(0, ge=0, le=1)
    aliquota_irrf: float = Field(0, ge=0, le=1)
    aliquota_csll: float = Field(0, ge=0, le=1)

    @field_validator("codigo")
    @classmethod
    def upper_codigo(cls, v: str) -> str:
        return v.strip().upper()


class TaxCodeCreate(TaxCodeBase):
    pass


class TaxCodeUpdate(BaseModel):
    descricao: Optional[str] = None
    aliquota_total: Optional[float] = None
    aliquota_iss: Optional[float] = None
    aliquota_pis: Optional[float] = None
    aliquota_cofins: Optional[float] = None
    aliquota_irrf: Optional[float] = None
    aliquota_csll: Optional[float] = None


class TaxCodeOut(TaxCodeBase):
    id: int
    ativo: bool
    criado_em: datetime
    criado_por: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Smoke import**

```powershell
cd backend
.venv\Scripts\activate
python -c "from app.models.tax_code import TaxCodeCreate, TaxCodeOut; print('ok')"
```

Esperado: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/tax_code.py
git commit -m "feat(financeiro-sap): Pydantic schemas TaxCode"
```

---

### Task 2: Constants enums

**Files:**
- Create: `backend/app/services/financeiro_enums.py`

- [ ] **Step 1: Criar arquivo de constantes**

```python
"""Enums SAP-like para classificacao de pagamentos."""
from __future__ import annotations

TIPOS_COBRANCA = ("mensal", "hora", "avulso", "exito", "prolabore", "partido")
NATUREZAS_PAGAMENTO = ("captacao", "performance", "captacao_performance", "projeto_opt")
TIPOS_DOCUMENTO = ("nf", "emitir", "recebimento_manual", "recibo")


def validar_tipo_cobranca(v: str | None) -> bool:
    return v is None or v in TIPOS_COBRANCA


def validar_natureza_pagamento(v: str | None) -> bool:
    return v is None or v in NATUREZAS_PAGAMENTO


def validar_tipo_documento(v: str) -> bool:
    return v in TIPOS_DOCUMENTO
```

- [ ] **Step 2: Smoke**

```powershell
cd backend
python -c "from app.services.financeiro_enums import TIPOS_COBRANCA, validar_tipo_cobranca; print(validar_tipo_cobranca('hora'), validar_tipo_cobranca('foo'))"
```

Esperado: `True False`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/financeiro_enums.py
git commit -m "feat(financeiro-sap): constants TIPOS_COBRANCA/NATUREZAS/TIPOS_DOCUMENTO"
```

---

### Task 3: SQLAlchemy `TaxCodeDB` + cols `ParticipacaoPagamentoDB`

**Files:**
- Modify: `backend/app/database.py` (add `TaxCodeDB` class + 6 cols em `ParticipacaoPagamentoDB`)

- [ ] **Step 1: Adicionar imports faltantes**

Localizar topo de `backend/app/database.py` na lista de imports do sqlalchemy. Garantir `Numeric` está incluído:

```python
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
    create_engine,
)
```

Se `Numeric` não estiver, adicionar.

- [ ] **Step 2: Criar classe `TaxCodeDB`**

Após classe `ParticipacaoPagamentoDB` (antes da função `init_db()`), adicionar:

```python
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
```

- [ ] **Step 3: Adicionar 6 colunas em `ParticipacaoPagamentoDB`**

Localizar classe `ParticipacaoPagamentoDB` em `backend/app/database.py`. Encontrar:

```python
    nf_referencia = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
```

Inserir antes de `created_at`:

```python
    tax_code_id = Column(Integer, ForeignKey("tax_codes.id"), nullable=True, index=True)
    valor_bruto = Column(Float, nullable=True)
    imposto_total = Column(Float, nullable=False, default=0)
    tipo_cobranca = Column(String(32), nullable=True)
    natureza_pagamento = Column(String(32), nullable=True, index=True)
    tipo_documento = Column(String(32), nullable=False, default="nf")
```

Observação: `nullable=True` para `tax_code_id` e `valor_bruto` durante transição (backfill na migration popula). Pydantic camada de service garante valores em writes novos.

- [ ] **Step 4: Smoke import**

```powershell
cd backend
python -c "from app.database import TaxCodeDB, ParticipacaoPagamentoDB; print(TaxCodeDB.__tablename__, [c.name for c in ParticipacaoPagamentoDB.__table__.columns if c.name in ('tax_code_id','valor_bruto','tipo_cobranca','natureza_pagamento','tipo_documento','imposto_total')])"
```

Esperado: `tax_codes ['tax_code_id', 'valor_bruto', 'imposto_total', 'tipo_cobranca', 'natureza_pagamento', 'tipo_documento']`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py
git commit -m "feat(financeiro-sap): TaxCodeDB model + 6 cols em participacao_pagamentos"
```

---

### Task 4: Migration `0005_tax_codes_sap_like.py`

**Files:**
- Create: `backend/alembic/versions/0005_tax_codes_sap_like.py`

- [ ] **Step 1: Criar migration**

```python
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
    op.add_column(
        "participacao_pagamentos",
        sa.Column("tax_code_id", sa.Integer, sa.ForeignKey("tax_codes.id"), nullable=True),
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
```

- [ ] **Step 2: Aplicar migration local**

```powershell
cd backend
.venv\Scripts\activate
alembic upgrade head
```

Esperado:
```
INFO  [alembic.runtime.migration] Running upgrade 0004_pagamento_parcelamento -> 0005_tax_codes_sap_like
```

- [ ] **Step 3: Verificar seed + backfill**

```powershell
python -c "from app.database import SessionLocal, TaxCodeDB; s=SessionLocal(); print(s.query(TaxCodeDB).all()); print([(p.tax_code_id, p.valor_bruto, p.imposto_total, p.tipo_documento) for p in __import__('app').database.SessionLocal().execute(__import__('sqlalchemy').text('SELECT tax_code_id, valor_bruto, imposto_total, tipo_documento FROM participacao_pagamentos LIMIT 5')).fetchall()])"
```

Esperado: 1+ TaxCodeDB. Rows pré-existentes têm `tax_code_id`, `valor_bruto`, `imposto_total`, `tipo_documento='nf'`.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/0005_tax_codes_sap_like.py
git commit -m "feat(financeiro-sap): migration 0005 (tax_codes + 6 cols + backfill PADRAO_1545)"
```

---

## Phase 2 — Backend Service + Endpoints

### Task 5: Service de cálculo SAP-like (TDD)

**Files:**
- Create: `backend/app/services/pagamento_calculator.py`
- Test: `backend/tests/test_pagamento_calculator.py`

- [ ] **Step 1: Escrever testes que falham**

```python
# backend/tests/test_pagamento_calculator.py
from decimal import Decimal

import pytest

from app.services.pagamento_calculator import calcular_componentes_pagamento


def test_calcula_imposto_e_liquido():
    out = calcular_componentes_pagamento(
        valor_bruto=10000.0,
        aliquota_total=0.1545,
        percentual_captacao=10.0,
        percentual_performance=0.0,
        discriminado=True,
        valor_contratual_informado=None,
    )
    assert out["imposto_total"] == 1545.00
    assert out["valor_liquido"] == 8455.00
    assert out["valor_contratual"] == 8455.00
    assert out["valor_participacao"] == 845.50


def test_split_5050_quando_nao_discriminado():
    out = calcular_componentes_pagamento(
        valor_bruto=10000.0,
        aliquota_total=0.1545,
        percentual_captacao=10.0,
        percentual_performance=10.0,
        discriminado=False,
        valor_contratual_informado=None,
    )
    # contratual = 8455 * 0.5 = 4227.50; participacao = 4227.50 * 20% = 845.50
    assert out["valor_contratual"] == 4227.50
    assert out["valor_participacao"] == 845.50


def test_aliquota_zero():
    out = calcular_componentes_pagamento(
        valor_bruto=1000.0,
        aliquota_total=0.0,
        percentual_captacao=20.0,
        percentual_performance=0.0,
        discriminado=True,
        valor_contratual_informado=None,
    )
    assert out["imposto_total"] == 0.0
    assert out["valor_liquido"] == 1000.0
    assert out["valor_participacao"] == 200.0


def test_valor_contratual_informado_override():
    out = calcular_componentes_pagamento(
        valor_bruto=10000.0,
        aliquota_total=0.1545,
        percentual_captacao=10.0,
        percentual_performance=0.0,
        discriminado=True,
        valor_contratual_informado=5000.0,
    )
    # quando informado, usa esse valor (alvara discrimina)
    assert out["valor_contratual"] == 5000.0
    assert out["valor_participacao"] == 500.0


def test_valor_bruto_negativo_raises():
    with pytest.raises(ValueError):
        calcular_componentes_pagamento(
            valor_bruto=-100.0, aliquota_total=0.1545, percentual_captacao=0,
            percentual_performance=0, discriminado=True, valor_contratual_informado=None,
        )


def test_aliquota_acima_de_um_raises():
    with pytest.raises(ValueError):
        calcular_componentes_pagamento(
            valor_bruto=1000.0, aliquota_total=1.1, percentual_captacao=0,
            percentual_performance=0, discriminado=True, valor_contratual_informado=None,
        )
```

- [ ] **Step 2: Rodar e ver falha**

```powershell
cd backend
.venv\Scripts\activate
pytest tests/test_pagamento_calculator.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.services.pagamento_calculator'`.

- [ ] **Step 3: Implementar service**

```python
# backend/app/services/pagamento_calculator.py
"""Calculo SAP-like: valor_bruto -> imposto -> liquido -> contratual -> participacao.

Replica formula da Planilha de Participacoes 2026:
- F = E * aliquota_total          (imposto)
- G = E - F                       (liquido contratual)
- H = G * (cap% + perf%) / 100   (participacao)
"""
from __future__ import annotations


def calcular_componentes_pagamento(
    *,
    valor_bruto: float,
    aliquota_total: float,
    percentual_captacao: float,
    percentual_performance: float,
    discriminado: bool,
    valor_contratual_informado: float | None,
) -> dict[str, float]:
    """Calcula imposto/liquido/contratual/participacao.

    Args:
        valor_bruto: Valor da NF (col E da planilha).
        aliquota_total: TaxCode aliquota_total (0 a 1).
        percentual_captacao: % captacao da ParticipacaoDB.
        percentual_performance: % performance da ParticipacaoDB.
        discriminado: Se True, alvara/acordo discrimina contratual.
        valor_contratual_informado: Se discriminado=True e usuario passou valor especifico
            (caso de alvara que discrimina exato), usa esse. Senao usa liquido inteiro.

    Returns:
        dict com chaves: imposto_total, valor_liquido, valor_contratual, valor_participacao.

    Raises:
        ValueError: valor_bruto < 0 ou aliquota_total fora de [0,1].
    """
    if valor_bruto < 0:
        raise ValueError(f"valor_bruto deve ser >= 0, recebido {valor_bruto}")
    if not (0 <= aliquota_total <= 1):
        raise ValueError(f"aliquota_total fora de [0,1]: {aliquota_total}")

    imposto_total = round(valor_bruto * aliquota_total, 2)
    valor_liquido = round(valor_bruto - imposto_total, 2)

    if discriminado:
        if valor_contratual_informado is not None:
            valor_contratual = round(valor_contratual_informado, 2)
        else:
            valor_contratual = valor_liquido
    else:
        # split 50/50 contratual / sucumbencial
        valor_contratual = round(valor_liquido * 0.5, 2)

    pct_efetivo = (percentual_captacao or 0.0) + (percentual_performance or 0.0)
    valor_participacao = round(valor_contratual * pct_efetivo / 100, 2)

    return {
        "imposto_total": imposto_total,
        "valor_liquido": valor_liquido,
        "valor_contratual": valor_contratual,
        "valor_participacao": valor_participacao,
    }
```

- [ ] **Step 4: Rodar tests — devem passar**

```powershell
pytest tests/test_pagamento_calculator.py -v
```

Esperado: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pagamento_calculator.py backend/tests/test_pagamento_calculator.py
git commit -m "feat(financeiro-sap): service calcular_componentes_pagamento (bruto->imposto->liquido->participacao)"
```

---

### Task 6: Router `tax_codes` (CRUD)

**Files:**
- Create: `backend/app/routers/tax_codes.py`

- [ ] **Step 1: Escrever testes**

Criar `backend/tests/test_tax_codes_router.py`:

```python
from fastapi.testclient import TestClient

import pytest

from app.main import app
from app.database import Base, engine, SessionLocal, TaxCodeDB


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    # cleanup tax_codes criados nos testes (mantem seed)
    with SessionLocal() as s:
        s.query(TaxCodeDB).filter(TaxCodeDB.codigo != "PADRAO_1545").delete()
        s.commit()


def _client_with_dev_user():
    c = TestClient(app)
    c.headers["X-Dev-User-Email"] = "financeiro@test.local"
    c.headers["X-Dev-User-Role"] = "financeiro"
    return c


def test_lista_tax_codes_inclui_padrao():
    c = _client_with_dev_user()
    r = c.get("/api/tax-codes")
    assert r.status_code == 200
    codigos = {tc["codigo"] for tc in r.json()}
    assert "PADRAO_1545" in codigos


def test_default_retorna_padrao():
    c = _client_with_dev_user()
    r = c.get("/api/tax-codes/default")
    assert r.status_code == 200
    assert r.json()["codigo"] == "PADRAO_1545"
    assert r.json()["aliquota_total"] == 0.1545


def test_cria_tax_code():
    c = _client_with_dev_user()
    r = c.post("/api/tax-codes", json={
        "codigo": "isento",
        "descricao": "Sem retencao",
        "aliquota_total": 0,
        "aliquota_iss": 0, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["codigo"] == "ISENTO"  # upper-cased
    assert body["ativo"] is True


def test_cria_duplicado_falha():
    c = _client_with_dev_user()
    payload = {
        "codigo": "DUP", "descricao": "x", "aliquota_total": 0,
        "aliquota_iss": 0, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    }
    c.post("/api/tax-codes", json=payload)
    r = c.post("/api/tax-codes", json=payload)
    assert r.status_code == 409


def test_patch_aliquota():
    c = _client_with_dev_user()
    r0 = c.post("/api/tax-codes", json={
        "codigo": "TEMP", "descricao": "tmp", "aliquota_total": 0.10,
        "aliquota_iss": 0.10, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    })
    tid = r0.json()["id"]
    r = c.patch(f"/api/tax-codes/{tid}", json={"aliquota_total": 0.05})
    assert r.status_code == 200
    assert r.json()["aliquota_total"] == 0.05


def test_desativar_padrao_falha():
    c = _client_with_dev_user()
    with SessionLocal() as s:
        padrao = s.query(TaxCodeDB).filter(TaxCodeDB.codigo == "PADRAO_1545").first()
        assert padrao is not None
        pid = padrao.id
    # tentar desativar com so 1 ativo
    r = c.post(f"/api/tax-codes/{pid}/desativar")
    # deve falhar pois eh o unico ativo
    assert r.status_code == 422


def test_role_advogado_bloqueado():
    c = TestClient(app)
    c.headers["X-Dev-User-Email"] = "adv@test.local"
    c.headers["X-Dev-User-Role"] = "advogado"
    r = c.get("/api/tax-codes")
    assert r.status_code == 403
```

- [ ] **Step 2: Rodar e ver falha**

```powershell
cd backend
pytest tests/test_tax_codes_router.py -v
```

Esperado: vários failures (404 ou import error de router).

- [ ] **Step 3: Implementar router**

```python
# backend/app/routers/tax_codes.py
"""CRUD de TaxCode (master data fiscal). Acesso: financeiro/admin."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_financeiro
from app.database import TaxCodeDB, get_db
from app.models.tax_code import TaxCodeCreate, TaxCodeOut, TaxCodeUpdate


router = APIRouter(prefix="/api/tax-codes", tags=["tax-codes"])


@router.get("", response_model=list[TaxCodeOut])
def listar(
    incluir_inativos: bool = False,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    q = db.query(TaxCodeDB)
    if not incluir_inativos:
        q = q.filter(TaxCodeDB.ativo == True)  # noqa: E712
    return q.order_by(TaxCodeDB.codigo).all()


@router.get("/default", response_model=TaxCodeOut)
def get_default(
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    tc = (
        db.query(TaxCodeDB)
        .filter(TaxCodeDB.codigo == "PADRAO_1545", TaxCodeDB.ativo == True)  # noqa: E712
        .first()
    )
    if not tc:
        raise HTTPException(404, "Tax code default 'PADRAO_1545' nao encontrado")
    return tc


@router.post("", response_model=TaxCodeOut, status_code=status.HTTP_201_CREATED)
def criar(
    body: TaxCodeCreate,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    tc = TaxCodeDB(
        codigo=body.codigo,
        descricao=body.descricao,
        aliquota_total=body.aliquota_total,
        aliquota_iss=body.aliquota_iss,
        aliquota_pis=body.aliquota_pis,
        aliquota_cofins=body.aliquota_cofins,
        aliquota_irrf=body.aliquota_irrf,
        aliquota_csll=body.aliquota_csll,
        ativo=True,
        criado_em=datetime.now(timezone.utc),
        criado_por=user.email,
    )
    db.add(tc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Codigo '{body.codigo}' ja existe")
    db.refresh(tc)
    return tc


@router.patch("/{tax_code_id}", response_model=TaxCodeOut)
def atualizar(
    tax_code_id: int,
    body: TaxCodeUpdate,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    tc = db.query(TaxCodeDB).filter(TaxCodeDB.id == tax_code_id).first()
    if not tc:
        raise HTTPException(404, "Tax code nao encontrado")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(tc, field, val)
    db.commit()
    db.refresh(tc)
    return tc


@router.post("/{tax_code_id}/desativar", response_model=TaxCodeOut)
def desativar(
    tax_code_id: int,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    tc = db.query(TaxCodeDB).filter(TaxCodeDB.id == tax_code_id).first()
    if not tc:
        raise HTTPException(404, "Tax code nao encontrado")

    # garante pelo menos 1 ativo
    ativos_count = (
        db.query(TaxCodeDB).filter(TaxCodeDB.ativo == True).count()  # noqa: E712
    )
    if tc.ativo and ativos_count <= 1:
        raise HTTPException(422, "Pelo menos um tax_code deve estar ativo")

    tc.ativo = False
    db.commit()
    db.refresh(tc)
    return tc
```

- [ ] **Step 4: Wire router em `main.py`**

Em `backend/app/main.py` localizar bloco de imports de routers:

```python
from app.routers import admin_credenciais, cnpj, contract, contracts, docuseal, email, nfse, nfse_internal, participacoes, users
```

Adicionar `tax_codes`:

```python
from app.routers import admin_credenciais, cnpj, contract, contracts, docuseal, email, nfse, nfse_internal, participacoes, tax_codes, users
```

E onde routers são incluídos via `app.include_router(...)`, adicionar:

```python
app.include_router(tax_codes.router)
```

- [ ] **Step 5: Rodar tests — devem passar**

```powershell
pytest tests/test_tax_codes_router.py -v
```

Esperado: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/tax_codes.py backend/app/main.py backend/tests/test_tax_codes_router.py
git commit -m "feat(financeiro-sap): router tax_codes (CRUD + wire) + 7 tests"
```

---

### Task 7: Refactor `RegistrarPagamentoRequest` + endpoint pagamentos

**Files:**
- Modify: `backend/app/routers/participacoes.py`

- [ ] **Step 1: Adicionar imports + constants**

No topo de `backend/app/routers/participacoes.py`, garantir imports:

```python
from app.database import (
    AuditLogDB,
    ContractDB,
    ParticipacaoDB,
    ParticipacaoPagamentoDB,
    TaxCodeDB,
    get_db,
    utcnow,
)
from app.services.financeiro_enums import (
    NATUREZAS_PAGAMENTO,
    TIPOS_COBRANCA,
    TIPOS_DOCUMENTO,
)
from app.services.pagamento_calculator import calcular_componentes_pagamento
```

- [ ] **Step 2: Expandir `RegistrarPagamentoRequest`**

Localizar `class RegistrarPagamentoRequest(BaseModel):`. Substituir pelo bloco abaixo:

```python
class RegistrarPagamentoRequest(BaseModel):
    data_recebimento: date
    valor_bruto: float                    # NOVO: passa a ser obrigatorio (planilha col E)
    discriminado: bool = True
    valor_contratual: Optional[float] = None
    observacoes: Optional[str] = None
    status: str = "aguardando_pagamento"
    parcela_num: int = 1
    parcela_total: int = 1
    nf_referencia: Optional[str] = None
    tax_code_id: Optional[int] = None     # NOVO: se None, usa PADRAO_1545
    tipo_cobranca: Optional[str] = None   # NOVO: enum TIPOS_COBRANCA
    natureza_pagamento: Optional[str] = None  # NOVO: enum NATUREZAS_PAGAMENTO
    tipo_documento: str = "nf"            # NOVO: enum TIPOS_DOCUMENTO
```

- [ ] **Step 3: Expandir `PagamentoResponse`**

Localizar `class PagamentoResponse(BaseModel):`. Substituir por:

```python
class PagamentoResponse(BaseModel):
    id: int
    participacao_id: int
    data_recebimento: str
    valor_bruto: Optional[float]
    imposto_total: float
    valor_liquido_recebido: float
    valor_participacao: float
    dentro_limite_temporal: bool
    observacoes: Optional[str]
    status: str
    parcela_num: int
    parcela_total: int
    nf_referencia: Optional[str]
    tax_code_id: Optional[int]
    tax_code_codigo: Optional[str]
    aliquota_aplicada: Optional[float]
    tipo_cobranca: Optional[str]
    natureza_pagamento: Optional[str]
    tipo_documento: str
    created_at: str
```

- [ ] **Step 4: Adicionar helper `_pagamento_response` antes do POST**

Localizar `@router.post("/{pid}/pagamentos"`. Acima dele inserir:

```python
def _pagamento_response(pag: ParticipacaoPagamentoDB, tc: TaxCodeDB | None) -> PagamentoResponse:
    return PagamentoResponse(
        id=pag.id,
        participacao_id=pag.participacao_id,
        data_recebimento=pag.data_recebimento.isoformat(),
        valor_bruto=pag.valor_bruto,
        imposto_total=pag.imposto_total or 0,
        valor_liquido_recebido=pag.valor_liquido_recebido,
        valor_participacao=pag.valor_participacao,
        dentro_limite_temporal=pag.dentro_limite_temporal,
        observacoes=pag.observacoes,
        status=pag.status,
        parcela_num=pag.parcela_num,
        parcela_total=pag.parcela_total,
        nf_referencia=pag.nf_referencia,
        tax_code_id=pag.tax_code_id,
        tax_code_codigo=tc.codigo if tc else None,
        aliquota_aplicada=float(tc.aliquota_total) if tc else None,
        tipo_cobranca=pag.tipo_cobranca,
        natureza_pagamento=pag.natureza_pagamento,
        tipo_documento=pag.tipo_documento or "nf",
        created_at=pag.created_at.isoformat(),
    )
```

- [ ] **Step 5: Substituir corpo do `registrar_pagamento`**

Localizar `def registrar_pagamento(` e substituir TODO o corpo da função (entre `def` e `return`) por:

```python
def registrar_pagamento(
    pid: int,
    body: RegistrarPagamentoRequest,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    p = db.query(ParticipacaoDB).filter(ParticipacaoDB.id == pid).first()
    if not p:
        raise HTTPException(404, "Participação não encontrada")

    if body.status not in PAGAMENTO_STATUS_VALIDOS:
        raise HTTPException(422, f"status invalido. Aceitos: {PAGAMENTO_STATUS_VALIDOS}")
    if body.parcela_num < 1 or body.parcela_total < 1 or body.parcela_num > body.parcela_total:
        raise HTTPException(422, "parcela_num/parcela_total invalidos (1<=num<=total)")
    if body.tipo_documento not in TIPOS_DOCUMENTO:
        raise HTTPException(422, f"tipo_documento invalido. Aceitos: {TIPOS_DOCUMENTO}")
    if body.tipo_cobranca is not None and body.tipo_cobranca not in TIPOS_COBRANCA:
        raise HTTPException(422, f"tipo_cobranca invalido. Aceitos: {TIPOS_COBRANCA}")
    if body.natureza_pagamento is not None and body.natureza_pagamento not in NATUREZAS_PAGAMENTO:
        raise HTTPException(422, f"natureza_pagamento invalida. Aceitos: {NATUREZAS_PAGAMENTO}")

    # Resolve tax code
    if body.tax_code_id is not None:
        tc = db.query(TaxCodeDB).filter(TaxCodeDB.id == body.tax_code_id).first()
        if not tc:
            raise HTTPException(422, f"tax_code_id {body.tax_code_id} nao encontrado")
        if not tc.ativo:
            raise HTTPException(422, "Tax code desativado, escolha outro")
    else:
        tc = (
            db.query(TaxCodeDB)
            .filter(TaxCodeDB.codigo == "PADRAO_1545", TaxCodeDB.ativo == True)  # noqa: E712
            .first()
        )
        if not tc:
            raise HTTPException(500, "PADRAO_1545 ausente — rodar migration 0005")

    # Calculo
    comp = calcular_componentes_pagamento(
        valor_bruto=body.valor_bruto,
        aliquota_total=float(tc.aliquota_total),
        percentual_captacao=p.percentual_captacao,
        percentual_performance=p.percentual_performance,
        discriminado=body.discriminado,
        valor_contratual_informado=body.valor_contratual if body.discriminado else None,
    )

    # Limite temporal: replica calcular_valor_participacao p/ dentro_limite_temporal
    from app.services.participacao_calculator import calcular_valor_participacao  # type: ignore
    resultado = calcular_valor_participacao(
        valor_liquido_recebido=comp["valor_contratual"],
        percentual_captacao=p.percentual_captacao,
        percentual_performance=p.percentual_performance,
        tipo_honorario=p.tipo_honorario,
        data_inicio_participacao=p.data_inicio,
        data_recebimento=body.data_recebimento,
        vinculo_ativo=p.vinculo_ativo,
        data_fim_vinculo=p.data_fim_vinculo,
        eh_contratual=True,
    )

    # Se calculo de limite/vinculo zerou, sobrescreve participacao por 0 mas mantem componentes
    valor_participacao_final = (
        comp["valor_participacao"]
        if resultado.dentro_limite_temporal and p.vinculo_ativo
        else 0.0
    )

    pag = ParticipacaoPagamentoDB(
        participacao_id=p.id,
        data_recebimento=body.data_recebimento,
        valor_bruto=body.valor_bruto,
        imposto_total=comp["imposto_total"],
        valor_liquido_recebido=comp["valor_contratual"],
        valor_participacao=valor_participacao_final,
        dentro_limite_temporal=resultado.dentro_limite_temporal,
        observacoes=(
            (body.observacoes or "")
            + (f" | {resultado.motivo_zerado}" if resultado.motivo_zerado else "")
        ).strip(" |") or None,
        status=body.status,
        parcela_num=body.parcela_num,
        parcela_total=body.parcela_total,
        nf_referencia=body.nf_referencia,
        tax_code_id=tc.id,
        tipo_cobranca=body.tipo_cobranca or p.tipo_honorario,
        natureza_pagamento=body.natureza_pagamento,
        tipo_documento=body.tipo_documento,
        registrado_por=user.email,
        created_at=utcnow(),
    )
    db.add(pag)
    db.commit()
    db.refresh(pag)
    return _pagamento_response(pag, tc)
```

- [ ] **Step 6: Atualizar `atualizar_status_pagamento` e `get_resumo` para usar `_pagamento_response`**

Localizar `def atualizar_status_pagamento` — substituir o `return PagamentoResponse(...)` final por:

```python
    tc = db.query(TaxCodeDB).filter(TaxCodeDB.id == pag.tax_code_id).first() if pag.tax_code_id else None
    return _pagamento_response(pag, tc)
```

Localizar bloco no `get_resumo_participacao` que constrói `pagamentos = [PagamentoResponse(...) for pag in p.pagamentos]`. Substituir por:

```python
    # carrega tax_codes referenciados de uma so vez
    tc_ids = {pag.tax_code_id for pag in p.pagamentos if pag.tax_code_id}
    tcs_map = {
        tc.id: tc
        for tc in db.query(TaxCodeDB).filter(TaxCodeDB.id.in_(tc_ids)).all()
    } if tc_ids else {}

    pagamentos = [_pagamento_response(pag, tcs_map.get(pag.tax_code_id)) for pag in p.pagamentos]
```

- [ ] **Step 7: Tests novos endpoint**

Criar `backend/tests/test_pagamento_sap_endpoint.py`:

```python
from datetime import date
from fastapi.testclient import TestClient

import pytest

from app.main import app
from app.database import Base, engine, SessionLocal, ParticipacaoDB, TaxCodeDB


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def _client():
    c = TestClient(app)
    c.headers["X-Dev-User-Email"] = "fin@test.local"
    c.headers["X-Dev-User-Role"] = "financeiro"
    return c


def _criar_participacao() -> int:
    with SessionLocal() as s:
        p = ParticipacaoDB(
            contract_id="test-contract-sap",
            beneficiario_email="adv@x.com",
            beneficiario_nome="Adv",
            tipo_honorario="hora",
            percentual_captacao=10.0,
            percentual_performance=0.0,
            natureza="contratual",
            data_inicio=date(2024, 8, 1),
            vinculo_ativo=True,
            aprovada=True,
            created_by="seed",
        )
        s.add(p)
        s.commit()
        return p.id


def test_registra_pagamento_calcula_componentes_sap():
    pid = _criar_participacao()
    c = _client()
    r = c.post(f"/api/participacoes/{pid}/pagamentos", json={
        "data_recebimento": "2026-05-01",
        "valor_bruto": 10000.0,
        "discriminado": True,
        "tipo_documento": "nf",
        "nf_referencia": "NF2026.999",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valor_bruto"] == 10000.0
    assert body["imposto_total"] == 1545.0
    assert body["valor_liquido_recebido"] == 8455.0
    assert body["valor_participacao"] == 845.5
    assert body["tax_code_codigo"] == "PADRAO_1545"
    assert body["aliquota_aplicada"] == 0.1545


def test_tipo_documento_invalido_422():
    pid = _criar_participacao()
    c = _client()
    r = c.post(f"/api/participacoes/{pid}/pagamentos", json={
        "data_recebimento": "2026-05-01",
        "valor_bruto": 1000.0,
        "tipo_documento": "xyz",
    })
    assert r.status_code == 422


def test_natureza_pagamento_invalida_422():
    pid = _criar_participacao()
    c = _client()
    r = c.post(f"/api/participacoes/{pid}/pagamentos", json={
        "data_recebimento": "2026-05-01",
        "valor_bruto": 1000.0,
        "natureza_pagamento": "nao_existe",
    })
    assert r.status_code == 422


def test_tax_code_desativado_422():
    # criar tax code, desativar, tentar usar
    pid = _criar_participacao()
    c = _client()
    r0 = c.post("/api/tax-codes", json={
        "codigo": "TMP_DESATIVAR", "descricao": "x", "aliquota_total": 0.10,
        "aliquota_iss": 0, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    })
    tid = r0.json()["id"]
    c.post(f"/api/tax-codes/{tid}/desativar")
    r = c.post(f"/api/participacoes/{pid}/pagamentos", json={
        "data_recebimento": "2026-05-01",
        "valor_bruto": 1000.0,
        "tax_code_id": tid,
    })
    assert r.status_code == 422
```

- [ ] **Step 8: Rodar suite completa**

```powershell
cd backend
pytest tests/ --ignore=tests/integration -q
```

Esperado: todos passam (60 atuais + ~10 novos = ~70 passed).

- [ ] **Step 9: Commit**

```bash
git add backend/app/routers/participacoes.py backend/tests/test_pagamento_sap_endpoint.py
git commit -m "feat(financeiro-sap): pagamento endpoint usa TaxCode + enums + calculo SAP-like"
```

---

## Phase 3 — Frontend

### Task 8: Cliente API finance

**Files:**
- Create: `frontend/src/app/lib/finance-api.ts`

- [ ] **Step 1: Criar cliente**

```typescript
// frontend/src/app/lib/finance-api.ts
import { getAuthHeaders } from "./api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

export interface TaxCode {
  id: number;
  codigo: string;
  descricao: string;
  aliquota_total: number;
  aliquota_iss: number;
  aliquota_pis: number;
  aliquota_cofins: number;
  aliquota_irrf: number;
  aliquota_csll: number;
  ativo: boolean;
  criado_em: string;
  criado_por: string;
}

export interface TaxCodeCreate {
  codigo: string;
  descricao: string;
  aliquota_total: number;
  aliquota_iss: number;
  aliquota_pis: number;
  aliquota_cofins: number;
  aliquota_irrf: number;
  aliquota_csll: number;
}

export type TipoCobranca = "mensal" | "hora" | "avulso" | "exito" | "prolabore" | "partido";
export type NaturezaPagamento = "captacao" | "performance" | "captacao_performance" | "projeto_opt";
export type TipoDocumento = "nf" | "emitir" | "recebimento_manual" | "recibo";

export const TIPOS_COBRANCA: TipoCobranca[] = ["mensal", "hora", "avulso", "exito", "prolabore", "partido"];
export const NATUREZAS_PAGAMENTO: NaturezaPagamento[] = ["captacao", "performance", "captacao_performance", "projeto_opt"];
export const TIPOS_DOCUMENTO: TipoDocumento[] = ["nf", "emitir", "recebimento_manual", "recibo"];

export const LABEL_TIPO_COBRANCA: Record<TipoCobranca, string> = {
  mensal: "Mensal",
  hora: "Hora trabalhada",
  avulso: "Avulso",
  exito: "Êxito",
  prolabore: "Pró-labore",
  partido: "Partido",
};

export const LABEL_NATUREZA: Record<NaturezaPagamento, string> = {
  captacao: "Captação",
  performance: "Performance",
  captacao_performance: "Captação + Performance",
  projeto_opt: "Projeto OpT",
};

export const LABEL_TIPO_DOC: Record<TipoDocumento, string> = {
  nf: "NF emitida",
  emitir: "A emitir",
  recebimento_manual: "Recebimento manual",
  recibo: "Recibo",
};

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...getAuthHeaders(), "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const taxCodeApi = {
  listar: (incluirInativos = false) =>
    _fetch<TaxCode[]>(`/api/tax-codes?incluir_inativos=${incluirInativos}`),
  getDefault: () => _fetch<TaxCode>("/api/tax-codes/default"),
  criar: (body: TaxCodeCreate) =>
    _fetch<TaxCode>("/api/tax-codes", { method: "POST", body: JSON.stringify(body) }),
  atualizar: (id: number, body: Partial<TaxCodeCreate>) =>
    _fetch<TaxCode>(`/api/tax-codes/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  desativar: (id: number) =>
    _fetch<TaxCode>(`/api/tax-codes/${id}/desativar`, { method: "POST" }),
};
```

- [ ] **Step 2: tsc check**

```powershell
cd frontend
npx tsc --noEmit
```

Esperado: sem erros.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/lib/finance-api.ts
git commit -m "feat(financeiro-ui): cliente API tax-codes + enums + labels"
```

---

### Task 9: Componente `AbaImpostos`

**Files:**
- Create: `frontend/src/components/financeiro/AbaImpostos.tsx`

- [ ] **Step 1: Criar componente**

```tsx
// frontend/src/components/financeiro/AbaImpostos.tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { taxCodeApi, type TaxCode, type TaxCodeCreate } from "@/app/lib/finance-api";

const EMPTY: TaxCodeCreate = {
  codigo: "",
  descricao: "",
  aliquota_total: 0,
  aliquota_iss: 0,
  aliquota_pis: 0,
  aliquota_cofins: 0,
  aliquota_irrf: 0,
  aliquota_csll: 0,
};

function pct(v: number) {
  return `${(v * 100).toFixed(2)}%`;
}

export function AbaImpostos() {
  const [items, setItems] = useState<TaxCode[]>([]);
  const [form, setForm] = useState<TaxCodeCreate>(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    taxCodeApi
      .listar(true)
      .then(setItems)
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // recalc aliquota_total = soma das individuais
  useEffect(() => {
    const total =
      form.aliquota_iss +
      form.aliquota_pis +
      form.aliquota_cofins +
      form.aliquota_irrf +
      form.aliquota_csll;
    setForm((f) => ({ ...f, aliquota_total: Number(total.toFixed(4)) }));
    // intencionalmente nao depende de form.aliquota_total para evitar loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    form.aliquota_iss,
    form.aliquota_pis,
    form.aliquota_cofins,
    form.aliquota_irrf,
    form.aliquota_csll,
  ]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      if (editingId) {
        await taxCodeApi.atualizar(editingId, form);
      } else {
        await taxCodeApi.criar(form);
      }
      setForm(EMPTY);
      setEditingId(null);
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "erro");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (tc: TaxCode) => {
    setForm({
      codigo: tc.codigo,
      descricao: tc.descricao,
      aliquota_total: tc.aliquota_total,
      aliquota_iss: tc.aliquota_iss,
      aliquota_pis: tc.aliquota_pis,
      aliquota_cofins: tc.aliquota_cofins,
      aliquota_irrf: tc.aliquota_irrf,
      aliquota_csll: tc.aliquota_csll,
    });
    setEditingId(tc.id);
  };

  const cancelEdit = () => {
    setForm(EMPTY);
    setEditingId(null);
  };

  const desativar = async (tc: TaxCode) => {
    if (!confirm(`Desativar ${tc.codigo}?`)) return;
    try {
      await taxCodeApi.desativar(tc.id);
      refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "erro");
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="bg-card border border-border rounded-lg p-4 space-y-3 text-sm">
        <h3 className="font-medium">{editingId ? "Editar Tax Code" : "Novo Tax Code"}</h3>
        <div className="grid md:grid-cols-2 gap-3">
          <label>
            <span className="block text-xs text-muted">Código</span>
            <input
              required
              disabled={!!editingId}
              value={form.codigo}
              onChange={(e) => setForm({ ...form, codigo: e.target.value })}
              className="w-full px-2 py-1 border border-border rounded font-mono uppercase"
            />
          </label>
          <label>
            <span className="block text-xs text-muted">Descrição</span>
            <input
              required
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              className="w-full px-2 py-1 border border-border rounded"
            />
          </label>
        </div>
        <div className="grid grid-cols-5 gap-2">
          {(["iss", "pis", "cofins", "irrf", "csll"] as const).map((k) => (
            <label key={k}>
              <span className="block text-xs text-muted uppercase">{k}</span>
              <input
                type="number"
                step={0.0001}
                min={0}
                max={1}
                value={form[`aliquota_${k}` as const]}
                onChange={(e) =>
                  setForm({ ...form, [`aliquota_${k}`]: parseFloat(e.target.value) || 0 })
                }
                className="w-full px-2 py-1 border border-border rounded"
              />
            </label>
          ))}
        </div>
        <p className="text-xs text-muted">
          Alíquota total (soma):{" "}
          <strong className="text-foreground">{pct(form.aliquota_total)}</strong>
        </p>
        {err && <div className="text-xs text-red-700">{err}</div>}
        <div className="flex gap-2">
          <button
            disabled={saving}
            className="px-3 py-1.5 bg-primary-dark text-white rounded text-xs disabled:opacity-50"
          >
            {saving ? "Salvando..." : editingId ? "Salvar alterações" : "Criar"}
          </button>
          {editingId && (
            <button
              type="button"
              onClick={cancelEdit}
              className="px-3 py-1.5 border border-border rounded text-xs"
            >
              Cancelar
            </button>
          )}
        </div>
      </form>

      <div>
        <h3 className="font-medium text-sm mb-2">Tax Codes cadastrados</h3>
        {loading ? (
          <p className="text-muted text-xs">Carregando...</p>
        ) : items.length === 0 ? (
          <p className="text-muted text-xs">Nenhum cadastrado.</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="text-muted border-b border-border">
              <tr>
                <th className="text-left py-2">Código</th>
                <th className="text-left py-2">Descrição</th>
                <th className="text-right py-2">Total</th>
                <th className="text-right py-2">ISS</th>
                <th className="text-right py-2">PIS</th>
                <th className="text-right py-2">COFINS</th>
                <th className="text-right py-2">IRRF</th>
                <th className="text-right py-2">CSLL</th>
                <th className="text-left py-2">Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((tc) => (
                <tr key={tc.id} className="border-b border-border/40">
                  <td className="py-2 font-mono">{tc.codigo}</td>
                  <td className="py-2">{tc.descricao}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_total)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_iss)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_pis)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_cofins)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_irrf)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_csll)}</td>
                  <td className="py-2">
                    {tc.ativo ? (
                      <span className="text-green-700">ativo</span>
                    ) : (
                      <span className="text-red-700">inativo</span>
                    )}
                  </td>
                  <td className="py-2 text-right space-x-2">
                    <button
                      onClick={() => startEdit(tc)}
                      className="text-xs text-accent hover:underline"
                    >
                      Editar
                    </button>
                    {tc.ativo && (
                      <button
                        onClick={() => desativar(tc)}
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

- [ ] **Step 2: tsc check**

```powershell
cd frontend
npx tsc --noEmit
```

Esperado: sem erros.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/financeiro/AbaImpostos.tsx
git commit -m "feat(financeiro-ui): AbaImpostos (CRUD tax_codes + form com soma alquota_total)"
```

---

### Task 10: Wire aba Impostos em `/financeiro`

**Files:**
- Modify: `frontend/src/app/financeiro/page.tsx`

- [ ] **Step 1: Import AbaImpostos no topo**

Localizar imports no início de `page.tsx` e adicionar:

```tsx
import { AbaImpostos } from "@/components/financeiro/AbaImpostos";
```

- [ ] **Step 2: Expandir tipo da tab**

Localizar:

```tsx
const [tab, setTab] = useState<"pendentes" | "lista" | "nova" | "simular" | "nfse">("pendentes");
```

Trocar para:

```tsx
const [tab, setTab] = useState<"pendentes" | "lista" | "nova" | "simular" | "nfse" | "impostos">("pendentes");
```

- [ ] **Step 3: Expandir nav loop**

Localizar:

```tsx
{(["pendentes", "lista", "nova", "simular", "nfse"] as const).map((t) => (
```

Trocar para:

```tsx
{(["pendentes", "lista", "nova", "simular", "nfse", "impostos"] as const).map((t) => (
```

E dentro do botão, no final dos `{t === "..." && ...}`, adicionar:

```tsx
{t === "impostos" && "Impostos"}
```

- [ ] **Step 4: Render condicional**

Localizar `{tab === "nfse" && <AbaNotasFiscais />}` e adicionar abaixo:

```tsx
{tab === "impostos" && <AbaImpostos />}
```

- [ ] **Step 5: tsc check**

```powershell
cd frontend
npx tsc --noEmit
```

Esperado: sem erros.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/financeiro/page.tsx
git commit -m "feat(financeiro-ui): aba Impostos em /financeiro"
```

---

### Task 11: `FormPagamento` expandido + tabela pagamentos

**Files:**
- Modify: `frontend/src/app/financeiro/page.tsx`
- Modify: `frontend/src/app/lib/api.ts` (atualiza `Pagamento` interface + `registrarPagamento` body)

- [ ] **Step 1: Atualizar `Pagamento` interface em `api.ts`**

Localizar `export interface Pagamento {` em `frontend/src/app/lib/api.ts` e substituir por:

```ts
export interface Pagamento {
  id: number;
  participacao_id: number;
  data_recebimento: string;
  valor_bruto: number | null;
  imposto_total: number;
  valor_liquido_recebido: number;
  valor_participacao: number;
  dentro_limite_temporal: boolean;
  observacoes: string | null;
  status: PagamentoStatus;
  parcela_num: number;
  parcela_total: number;
  nf_referencia: string | null;
  tax_code_id: number | null;
  tax_code_codigo: string | null;
  aliquota_aplicada: number | null;
  tipo_cobranca: string | null;
  natureza_pagamento: string | null;
  tipo_documento: string;
  created_at: string;
}
```

- [ ] **Step 2: Atualizar `registrarPagamento` body**

Localizar `export async function registrarPagamento(`. Substituir bloco do `body` por:

```ts
export async function registrarPagamento(
  pid: number,
  body: {
    data_recebimento: string;
    valor_bruto: number;
    discriminado: boolean;
    valor_contratual?: number;
    observacoes?: string;
    status?: PagamentoStatus;
    parcela_num?: number;
    parcela_total?: number;
    nf_referencia?: string;
    tax_code_id?: number;
    tipo_cobranca?: string;
    natureza_pagamento?: string;
    tipo_documento?: string;
  }
) {
```

- [ ] **Step 3: Importar taxCodeApi + enums no topo de `page.tsx`**

Em `frontend/src/app/financeiro/page.tsx`, adicionar abaixo dos imports `@/components/nfse`:

```tsx
import {
  taxCodeApi,
  TIPOS_COBRANCA,
  NATUREZAS_PAGAMENTO,
  TIPOS_DOCUMENTO,
  LABEL_TIPO_COBRANCA,
  LABEL_NATUREZA,
  LABEL_TIPO_DOC,
  type TaxCode,
} from "@/app/lib/finance-api";
```

- [ ] **Step 4: Substituir `FormPagamento` inteiro**

Localizar `function FormPagamento({` e substituir TODA a função por:

```tsx
function FormPagamento({
  participacaoId,
  onDone,
}: {
  participacaoId: number;
  onDone: () => void;
}) {
  const [taxCodes, setTaxCodes] = useState<TaxCode[]>([]);
  const [defaultTaxId, setDefaultTaxId] = useState<number | null>(null);
  const [form, setForm] = useState({
    data_recebimento: new Date().toISOString().slice(0, 10),
    valor_bruto: 0,
    discriminado: true,
    valor_contratual: 0,
    observacoes: "",
    parcela_num: 1,
    parcela_total: 1,
    nf_referencia: "",
    tax_code_id: 0,
    tipo_cobranca: "",
    natureza_pagamento: "",
    tipo_documento: "nf",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([taxCodeApi.listar(false), taxCodeApi.getDefault()])
      .then(([list, def]) => {
        setTaxCodes(list);
        setDefaultTaxId(def.id);
        setForm((f) => ({ ...f, tax_code_id: def.id }));
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  // preview calculo em tempo real
  const selectedTc = taxCodes.find((tc) => tc.id === form.tax_code_id);
  const aliquota = selectedTc?.aliquota_total ?? 0;
  const previewImposto = +(form.valor_bruto * aliquota).toFixed(2);
  const previewLiquido = +(form.valor_bruto - previewImposto).toFixed(2);
  const previewContratual = form.discriminado ? form.valor_contratual || previewLiquido : previewLiquido * 0.5;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    setSaving(true);
    try {
      await registrarPagamento(participacaoId, {
        data_recebimento: form.data_recebimento,
        valor_bruto: form.valor_bruto,
        discriminado: form.discriminado,
        valor_contratual: form.discriminado ? form.valor_contratual : undefined,
        observacoes: form.observacoes || undefined,
        parcela_num: form.parcela_num,
        parcela_total: form.parcela_total,
        nf_referencia: form.nf_referencia || undefined,
        tax_code_id: form.tax_code_id || undefined,
        tipo_cobranca: form.tipo_cobranca || undefined,
        natureza_pagamento: form.natureza_pagamento || undefined,
        tipo_documento: form.tipo_documento,
      });
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erro");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="bg-white border border-border rounded-lg p-4 space-y-3 text-xs"
    >
      <div className="grid grid-cols-2 gap-2">
        <label>
          <span className="block text-muted mb-1">Data recebimento</span>
          <input
            type="date"
            required
            value={form.data_recebimento}
            onChange={(e) => setForm({ ...form, data_recebimento: e.target.value })}
            className="input"
          />
        </label>
        <label>
          <span className="block text-muted mb-1">Valor bruto NF (R$)</span>
          <input
            type="number"
            step={0.01}
            required
            value={form.valor_bruto}
            onChange={(e) => setForm({ ...form, valor_bruto: parseFloat(e.target.value) || 0 })}
            className="input"
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <label>
          <span className="block text-muted mb-1">Código fiscal</span>
          <select
            value={form.tax_code_id}
            onChange={(e) => setForm({ ...form, tax_code_id: parseInt(e.target.value) || 0 })}
            className="input"
          >
            {taxCodes.map((tc) => (
              <option key={tc.id} value={tc.id}>
                {tc.codigo} ({(tc.aliquota_total * 100).toFixed(2)}%)
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="block text-muted mb-1">Tipo documento</span>
          <select
            value={form.tipo_documento}
            onChange={(e) => setForm({ ...form, tipo_documento: e.target.value })}
            className="input"
          >
            {TIPOS_DOCUMENTO.map((t) => (
              <option key={t} value={t}>{LABEL_TIPO_DOC[t]}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <label>
          <span className="block text-muted mb-1">Tipo cobrança</span>
          <select
            value={form.tipo_cobranca}
            onChange={(e) => setForm({ ...form, tipo_cobranca: e.target.value })}
            className="input"
          >
            <option value="">(herdar da participação)</option>
            {TIPOS_COBRANCA.map((t) => (
              <option key={t} value={t}>{LABEL_TIPO_COBRANCA[t]}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="block text-muted mb-1">Natureza</span>
          <select
            value={form.natureza_pagamento}
            onChange={(e) => setForm({ ...form, natureza_pagamento: e.target.value })}
            className="input"
          >
            <option value="">(usar da participação)</option>
            {NATUREZAS_PAGAMENTO.map((n) => (
              <option key={n} value={n}>{LABEL_NATUREZA[n]}</option>
            ))}
          </select>
        </label>
      </div>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={form.discriminado}
          onChange={(e) => setForm({ ...form, discriminado: e.target.checked })}
        />
        <span>Alvará/acordo discrimina parcela contratual?</span>
      </label>

      {form.discriminado && (
        <label>
          <span className="block text-muted mb-1">Parcela contratual informada (R$) — opcional</span>
          <input
            type="number"
            step={0.01}
            value={form.valor_contratual}
            onChange={(e) => setForm({ ...form, valor_contratual: parseFloat(e.target.value) || 0 })}
            placeholder="Deixe 0 para usar líquido inteiro"
            className="input"
          />
        </label>
      )}

      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-border/40">
        <label>
          <span className="block text-muted mb-1">Parcela nº</span>
          <input
            type="number"
            min={1}
            value={form.parcela_num}
            onChange={(e) => setForm({ ...form, parcela_num: parseInt(e.target.value) || 1 })}
            className="input"
          />
        </label>
        <label>
          <span className="block text-muted mb-1">Total parcelas</span>
          <input
            type="number"
            min={1}
            value={form.parcela_total}
            onChange={(e) => setForm({ ...form, parcela_total: parseInt(e.target.value) || 1 })}
            className="input"
          />
        </label>
        <label>
          <span className="block text-muted mb-1">NF referência</span>
          <input
            value={form.nf_referencia}
            onChange={(e) => setForm({ ...form, nf_referencia: e.target.value })}
            placeholder="NF2026.XXX ou emitir"
            className="input"
          />
        </label>
      </div>

      <label className="block">
        <span className="block text-muted mb-1">Observações</span>
        <input
          value={form.observacoes}
          onChange={(e) => setForm({ ...form, observacoes: e.target.value })}
          className="input"
        />
      </label>

      <div className="bg-gray-50 border border-border/40 rounded p-2 grid grid-cols-2 gap-2 text-[11px]">
        <span>Bruto: <strong>{brl(form.valor_bruto)}</strong></span>
        <span>Imposto ({(aliquota * 100).toFixed(2)}%): <strong>{brl(previewImposto)}</strong></span>
        <span>Líquido: <strong>{brl(previewLiquido)}</strong></span>
        <span>Contratual: <strong>{brl(previewContratual)}</strong></span>
      </div>

      {err && (
        <div className="rounded border border-red-200 bg-red-50 p-2 text-red-800">{err}</div>
      )}

      <button
        type="submit"
        disabled={saving || !form.tax_code_id || !form.valor_bruto}
        className="px-3 py-1.5 bg-primary-dark text-white rounded font-medium hover:bg-primary-dark/90 disabled:opacity-50"
      >
        {saving ? "Calculando..." : "Registrar e calcular participação"}
      </button>
    </form>
  );
}
```

- [ ] **Step 5: Atualizar tabela pagamentos**

Localizar dentro de `DetalheParticipacao`, a tabela `<table className="w-full text-xs mt-2">`. Substituir bloco `<thead>` por:

```tsx
              <thead>
                <tr className="text-muted border-b border-border">
                  <th className="text-left py-1">Data</th>
                  <th className="text-left py-1">NF</th>
                  <th className="text-left py-1">Parcela</th>
                  <th className="text-left py-1">Doc</th>
                  <th className="text-left py-1">Cobr</th>
                  <th className="text-left py-1">Natureza</th>
                  <th className="text-right py-1">Bruto</th>
                  <th className="text-right py-1">Imposto</th>
                  <th className="text-right py-1">Líquido</th>
                  <th className="text-right py-1">Participação</th>
                  <th className="text-left py-1">Status</th>
                  <th className="text-left py-1">Obs.</th>
                </tr>
              </thead>
```

E o bloco do mapping de linhas (`{resumo.pagamentos.map((pg) => (`) — substituir o `<tr>` inteiro por:

```tsx
                {resumo.pagamentos.map((pg) => (
                  <tr key={pg.id} className={`border-b border-border/40 ${rowBgByStatus(pg.status)}`}>
                    <td className="py-1">{pg.data_recebimento}</td>
                    <td className="py-1 font-mono text-[10px]">{pg.nf_referencia || "—"}</td>
                    <td className="py-1">
                      {pg.parcela_total > 1
                        ? `${pg.parcela_num}/${pg.parcela_total}`
                        : "Única"}
                    </td>
                    <td className="py-1 text-[10px]">{pg.tipo_documento}</td>
                    <td className="py-1 text-[10px]">{pg.tipo_cobranca || "—"}</td>
                    <td className="py-1 text-[10px]">{pg.natureza_pagamento || "—"}</td>
                    <td className="py-1 text-right">
                      {pg.valor_bruto != null ? brl(pg.valor_bruto) : "—"}
                    </td>
                    <td className="py-1 text-right">{brl(pg.imposto_total)}</td>
                    <td className="py-1 text-right">{brl(pg.valor_liquido_recebido)}</td>
                    <td className={`py-1 text-right ${pg.valor_participacao === 0 ? "text-red-700" : ""}`}>
                      {brl(pg.valor_participacao)}
                    </td>
                    <td className="py-1">
                      <StatusSelect
                        value={pg.status}
                        onChange={async (next) => {
                          try {
                            await atualizarStatusPagamento(pg.id, next);
                            reload();
                          } catch (e) {
                            alert(e instanceof Error ? e.message : "Erro ao atualizar status");
                          }
                        }}
                      />
                    </td>
                    <td className="py-1 text-muted text-[10px]">{pg.observacoes || ""}</td>
                  </tr>
                ))}
```

- [ ] **Step 6: Tornar tabela responsiva (overflow-x)**

Localizar o `<table className="w-full text-xs mt-2">`. Envolver em wrapper:

```tsx
            <div className="overflow-x-auto">
              <table className="w-full text-xs mt-2 min-w-[900px]">
                {/* ... (thead + tbody inalterados) ... */}
              </table>
            </div>
```

- [ ] **Step 7: tsc check**

```powershell
cd frontend
npx tsc --noEmit
```

Esperado: sem erros.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/financeiro/page.tsx frontend/src/app/lib/api.ts
git commit -m "feat(financeiro-ui): FormPagamento SAP-like + tabela pagamentos expandida"
```

---

## Phase 4 — Verification

### Task 12: Verification final

**Files:**
- (nenhum — task de execução)

- [ ] **Step 1: Backend unit suite**

```powershell
cd backend
.venv\Scripts\activate
pytest tests/ --ignore=tests/integration -v
```

Esperado: todos os testes verdes (60 anteriores + ~13 novos = ~73 passed).

- [ ] **Step 2: Frontend type check**

```powershell
cd frontend
npx tsc --noEmit
```

Esperado: sem erros.

- [ ] **Step 3: Smoke local backend**

```powershell
cd backend
$env:NFSE_ENABLED="false"
uvicorn app.main:app --port 8000
```

Em outro terminal:

```powershell
curl http://localhost:8000/api/tax-codes -H "X-Dev-User-Email: fin@test.local" -H "X-Dev-User-Role: financeiro"
```

Esperado: lista contendo `PADRAO_1545`.

- [ ] **Step 4: Smoke frontend**

```powershell
cd frontend
npm run dev
```

Abrir `http://localhost:3000/financeiro` logado como financeiro:
- Aba **Impostos** aparece com `PADRAO_1545`.
- Aba **Participações** → expandir uma → tabela com colunas Bruto/Imposto/Doc/Cobr/Natureza.
- "+ Registrar recebimento" abre form com selects + preview cálculo em tempo real.

- [ ] **Step 5: Push deploy + verificar Render**

```bash
git push origin master
```

Aguardar Render deploy (alembic upgrade aplica `0005_tax_codes_sap_like` automaticamente).

Logs esperados:
```
INFO  [alembic.runtime.migration] Running upgrade 0004_pagamento_parcelamento -> 0005_tax_codes_sap_like
```

Teste prod:
```bash
curl https://honorario-cf.onrender.com/api/tax-codes/default
```
Esperado (após auth): JSON do `PADRAO_1545`.

---

## Self-Review (executado durante a escrita)

### Spec coverage
- §Architecture/TaxCodeDB → Task 3, 4 ✓
- §Enums → Task 2 ✓
- §ParticipacaoPagamentoDB +6 cols → Task 3, 4 ✓
- §Data Flow (calcular_componentes_pagamento) → Task 5 ✓
- §Components/Backend (model, schemas, router, calculator) → Tasks 1, 5, 6 ✓
- §Components/Endpoints novos → Task 6 ✓
- §Components/Frontend (finance-api, AbaImpostos, FormPagamento, table) → Tasks 8, 9, 10, 11 ✓
- §Error Handling (enum 422, tax_code inativo 422, codigo duplicado 409, desativar ultimo 422) → Tasks 6, 7 ✓
- §Testing (test_tax_codes, test_pagamento_calculator, test_pagamento_sap_endpoint) → Tasks 5, 6, 7 ✓
- §Migration backfill → Task 4 ✓
- §Authorization (require_financeiro) → Task 6 ✓
- §Out of Scope (iss_municipio, import CSV, RFB API, internal_orders) — não implementado, conforme decisão ✓

### Placeholder scan
- Nenhum "TBD"/"TODO"/"implement later" nas tasks.
- Backfill calcula `valor_bruto` reverso explicitamente com fórmula `liquido / (1 - 0.1545)`.

### Type consistency
- `TaxCodeDB.aliquota_total: Numeric(5,4)` em model + migration ✓
- `calcular_componentes_pagamento` retorna `dict[str, float]` consistente em test + service + uso no router ✓
- `PagamentoResponse.aliquota_aplicada: Optional[float]` — convertido de `Numeric` para `float` no helper `_pagamento_response` ✓
- `taxCodeApi.criar` body type `TaxCodeCreate` match com backend Pydantic `TaxCodeCreate` ✓

### Gaps detectados
- `_pagamento_response` helper consolidado para evitar duplicação (3 lugares usavam `PagamentoResponse(...)` manualmente) ✓
- Decisão sobre `valor_bruto` nullable=True em ParticipacaoPagamentoDB: necessário para migração; novas writes via endpoint sempre populam ✓
- Backfill `tipo_cobranca` herda de `participacoes.tipo_honorario` que pode ter valores fora de `TIPOS_COBRANCA` (ex: `partido`, `prolabore` que estão; mas `misto` não está em `TIPOS_COBRANCA`). Decision: aceitar valores legados sem validar — apenas valida em writes novos ✓
