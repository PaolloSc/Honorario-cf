# Participação — campos estruturados Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Etapa 5 (Participação) com tipo de valor (radio: percentual/valor/outro), seleção de advogados (multi em "para quem", único nos responsáveis) e contato em 3 campos; backend estruturado com migração compatível.

**Architecture:** Novo endpoint não-admin lista colaboradores. `Participacao` (backend + frontend) ganha campos estruturados com validator de migração de dados antigos. Step5 reescreve a UI; Step7 passa os campos novos na ficha do financeiro; `email.py` renderiza a ficha a partir dos novos campos com fallback p/ legado.

**Tech Stack:** FastAPI/Pydantic/pytest (backend); Next.js 15/React 19/TypeScript/Tailwind (frontend, verificação por `npm run build`). Reúsa `CurrencyInput.tsx`.

**Diretório:** paths relativas a `C:/Users/paollo/Downloads/Codigo/Honorario-cf`. Branch atual: `feature/participacao-estruturada`.

**Comandos:**
- Backend test: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest <arquivo> -v` (rodar de `backend/`).
- Frontend build: `cd frontend` + `npm run build`.

---

## Task 1: Backend — endpoint `GET /api/users/colaboradores` (não-admin)

**Files:**
- Modify: `backend/app/routers/users.py`
- Test: `backend/tests/test_colaboradores.py` (criar)

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_colaboradores.py`:

```python
"""GET /api/users/colaboradores: lista colaboradores p/ qualquer usuario logado."""
from types import SimpleNamespace

from app.main import app
from app.auth import get_current_user
from app.database import UserDB, get_db


def _seed_users(client):
    # usa a mesma engine de teste via get_db override do app
    gen = app.dependency_overrides.get(get_db)
    # cria direto pela sessao da app
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.add(UserDB(azure_id="z1", email="bruno@cf.com", name="Bruno Advogado", role="advogado"))
        db.add(UserDB(azure_id="a1", email="ana@cf.com", name="Ana Admin", role="admin"))
        db.commit()
    finally:
        db.close()


def test_colaboradores_requires_auth(client):
    resp = client.get("/api/users/colaboradores")
    assert resp.status_code in (401, 403)


def test_colaboradores_lists_all_sorted_by_name(client):
    _seed_users(client)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        azure_id="x", email="x@x.com", name="X", role="advogado"
    )
    try:
        resp = client.get("/api/users/colaboradores")
        assert resp.status_code == 200
        data = resp.json()
        nomes = [c["name"] for c in data["colaboradores"]]
        assert nomes == ["Ana Admin", "Bruno Advogado"]  # ordenado por nome
        assert data["colaboradores"][0]["email"] == "ana@cf.com"
        assert data["colaboradores"][0]["role"] == "admin"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/test_colaboradores.py -v`
Expected: `test_colaboradores_lists_all_sorted_by_name` FALHA (404 — rota inexistente).

- [ ] **Step 3: Implementar o endpoint**

Em `backend/app/routers/users.py`, adicionar uma resposta e a rota. Após a classe `UserListResponse` (linha ~26), adicionar:

```python
class ColaboradorOut(BaseModel):
    name: str
    email: str
    role: str


class ColaboradoresResponse(BaseModel):
    colaboradores: list[ColaboradorOut]
```

E adicionar a rota (após `get_me`, antes de `list_users`):

```python
@router.get("/colaboradores", response_model=ColaboradoresResponse)
def list_colaboradores(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista todos os usuarios (nome/email/role) para seleção no wizard. Qualquer usuario logado."""
    users = db.query(UserDB).order_by(UserDB.name).all()
    return ColaboradoresResponse(
        colaboradores=[
            ColaboradorOut(name=u.name, email=u.email, role=u.role) for u in users
        ]
    )
```

> Importante: declarar `/colaboradores` ANTES de qualquer rota com path param que possa capturá-la. Aqui as outras rotas são `""`, `/me` e `/{user_id}/role` — `/colaboradores` não conflita com `/{user_id}/role` (segmentos distintos), mas mantenha a rota literal antes da `@router.patch("/{user_id}/role")` por clareza.

- [ ] **Step 4: Rodar e ver passar**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/test_colaboradores.py -v`
Expected: 2 passed.

- [ ] **Step 5: Suíte backend**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/ --ignore=tests/integration -q`
Expected: tudo verde (sem novos erros).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/users.py backend/tests/test_colaboradores.py
git commit -m "feat(users): endpoint /api/users/colaboradores nao-admin"
```

---

## Task 2: Backend — `Participacao` model com campos estruturados + migração

**Files:**
- Modify: `backend/app/models/contract.py` (classe `Participacao`, ~linha 221-240)
- Test: `backend/tests/test_participacao_model.py` (criar)

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_participacao_model.py`:

```python
"""Participacao: campos estruturados + migracao de dados antigos."""
from app.models.contract import Participacao


def test_novos_campos_estruturados():
    p = Participacao(
        tem_participacao=True,
        valor_tipo="percentual",
        valor_percentual="10",
        para_quem=["Bruno Advogado", "Ana Admin"],
        contato_financeiro_nome="Carlos",
        contato_financeiro_email="carlos@cli.com",
        contato_financeiro_telefone="(31) 99999-0000",
    )
    assert p.valor_tipo == "percentual"
    assert p.valor_percentual == "10"
    assert p.para_quem == ["Bruno Advogado", "Ana Admin"]
    assert p.contato_financeiro_email == "carlos@cli.com"


def test_migra_valor_legado_para_outro():
    # dado antigo: percentual_ou_valor string, sem valor_tipo
    p = Participacao(tem_participacao=True, percentual_ou_valor="20% sobre exito")
    assert p.valor_tipo == "outro"
    assert p.valor_outro == "20% sobre exito"


def test_migra_para_quem_string_para_lista():
    p = Participacao(tem_participacao=True, para_quem="Bruno Advogado")
    assert p.para_quem == ["Bruno Advogado"]


def test_para_quem_vazio_vira_lista_vazia():
    p = Participacao(tem_participacao=True, para_quem="")
    assert p.para_quem == []


def test_valor_monetario_float():
    p = Participacao(tem_participacao=True, valor_tipo="valor", valor_monetario=5000.0)
    assert p.valor_monetario == 5000.0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/test_participacao_model.py -v`
Expected: falhas (campos inexistentes / sem migração).

- [ ] **Step 3: Atualizar o model**

Em `backend/app/models/contract.py`, substituir a classe `Participacao` inteira por:

```python
class Participacao(BaseModel):
    tem_participacao: bool = False
    # Valor (tipo + campo do tipo escolhido)
    valor_tipo: Optional[str] = None  # "percentual" | "valor" | "outro"
    valor_percentual: Optional[str] = None
    valor_monetario: Optional[float] = None
    valor_outro: Optional[str] = None
    # Advogados
    para_quem: list[str] = []
    natureza: Optional[str] = None
    responsavel_captacao: Optional[str] = None
    responsavel_gestao: Optional[str] = None
    # Contato financeiro do cliente (3 campos)
    contato_financeiro_nome: Optional[str] = None
    contato_financeiro_email: Optional[str] = None
    contato_financeiro_telefone: Optional[str] = None
    # Legados (compat com contratos salvos antes desta mudanca)
    percentual_ou_valor: Optional[str] = None
    contato_financeiro_cliente: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_and_migrate(cls, data):
        if not isinstance(data, dict):
            return data
        # None -> "" para campos string
        for field in ("natureza", "responsavel_captacao", "responsavel_gestao",
                      "valor_percentual", "valor_outro", "percentual_ou_valor",
                      "contato_financeiro_nome", "contato_financeiro_email",
                      "contato_financeiro_telefone", "contato_financeiro_cliente"):
            if data.get(field) is None:
                data[field] = ""
        # para_quem: string antiga -> lista
        pq = data.get("para_quem")
        if isinstance(pq, str):
            data["para_quem"] = [pq] if pq.strip() else []
        elif pq is None:
            data["para_quem"] = []
        # valor legado -> tipo "outro"
        if not data.get("valor_tipo") and data.get("percentual_ou_valor"):
            data["valor_tipo"] = "outro"
            if not data.get("valor_outro"):
                data["valor_outro"] = data["percentual_ou_valor"]
        return data
```

> Confirme que `model_validator` e `Optional` já estão importados no topo do arquivo (o `_coerce_nulls` antigo usava `model_validator`; `Optional` já é usado). Não há mais o método `_coerce_nulls` antigo — ele foi substituído por `_coerce_and_migrate`.

- [ ] **Step 4: Rodar e ver passar**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/test_participacao_model.py -v`
Expected: 5 passed.

- [ ] **Step 5: Suíte backend (garante que nada quebrou — ex: test_bugfixes usa Participacao)**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/ --ignore=tests/integration -q`
Expected: verde. Se `test_bugfixes.py` (TestParticipacaoNullCoercion) falhar, verificar que os campos que ele testa (`para_quem`, etc.) ainda coagem None→""; o novo validator cobre isso, exceto `para_quem` que agora vira `[]` — ajustar a expectativa SÓ se o teste pré-existente checar `para_quem == ""` (nesse caso, é mudança intencional; atualizar o teste para `== []`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/contract.py backend/tests/test_participacao_model.py
git commit -m "feat(participacao): campos estruturados no model + migracao legado"
```

---

## Task 3: Backend — ficha do financeiro (`email.py`) com campos novos

**Files:**
- Modify: `backend/app/routers/email.py` (`ParticipacaoEmailRequest` ~linha 31-50; montagem de `rows` ~linha 296-307)
- Test: `backend/tests/test_participacao_ficha.py` (criar)

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_participacao_ficha.py`:

```python
"""ParticipacaoEmailRequest: novos campos + migracao."""
from app.routers.email import ParticipacaoEmailRequest


def test_request_aceita_campos_novos():
    r = ParticipacaoEmailRequest(
        contract_id="c1",
        cliente_nome="Cliente",
        valor_tipo="valor",
        valor_monetario=5000.0,
        para_quem=["Bruno", "Ana"],
        contato_financeiro_nome="Carlos",
        contato_financeiro_email="c@x.com",
        contato_financeiro_telefone="(31) 99999-0000",
    )
    assert r.valor_tipo == "valor"
    assert r.valor_monetario == 5000.0
    assert r.para_quem == ["Bruno", "Ana"]
    assert r.contato_financeiro_email == "c@x.com"


def test_request_migra_para_quem_string():
    r = ParticipacaoEmailRequest(contract_id="c1", cliente_nome="X", para_quem="Bruno")
    assert r.para_quem == ["Bruno"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/test_participacao_ficha.py -v`
Expected: falha (campos inexistentes).

- [ ] **Step 3: Atualizar `ParticipacaoEmailRequest`**

Em `backend/app/routers/email.py`, substituir a classe `ParticipacaoEmailRequest` por:

```python
class ParticipacaoEmailRequest(BaseModel):
    contract_id: str
    cliente_nome: str
    objeto_contrato: str = ""
    # Valor estruturado
    valor_tipo: str = ""           # "percentual" | "valor" | "outro"
    valor_percentual: str = ""
    valor_monetario: float | None = None
    valor_outro: str = ""
    # Advogados
    para_quem: list[str] = []
    natureza: str = ""
    responsavel_captacao: str = ""
    responsavel_gestao: str = ""
    # Contato financeiro (3 campos)
    contato_financeiro_nome: str = ""
    contato_financeiro_email: str = ""
    contato_financeiro_telefone: str = ""
    # Legados
    percentual_ou_valor: str = ""
    contato_financeiro_cliente: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, data):
        if isinstance(data, dict):
            for field in ("objeto_contrato", "valor_tipo", "valor_percentual",
                          "valor_outro", "natureza", "responsavel_captacao",
                          "responsavel_gestao", "contato_financeiro_nome",
                          "contato_financeiro_email", "contato_financeiro_telefone",
                          "percentual_ou_valor", "contato_financeiro_cliente"):
                if data.get(field) is None:
                    data[field] = ""
            pq = data.get("para_quem")
            if isinstance(pq, str):
                data["para_quem"] = [pq] if pq.strip() else []
            elif pq is None:
                data["para_quem"] = []
        return data
```

- [ ] **Step 4: Atualizar a montagem das linhas da ficha**

Em `email.py`, substituir o trecho que monta `rows` para Percentual/Valor, Para quem e Contato (o bloco atual das linhas ~296-307). Substituir DE:

```python
        if data.percentual_ou_valor:
            rows.append(("Percentual/Valor", data.percentual_ou_valor))
        if data.para_quem:
            rows.append(("Para quem", data.para_quem))
        if data.natureza:
            rows.append(("Natureza", data.natureza))
        if data.responsavel_captacao:
            rows.append(("Resp. Captação", data.responsavel_captacao))
        if data.responsavel_gestao:
            rows.append(("Resp. Gestão", data.responsavel_gestao))
        if data.contato_financeiro_cliente:
            rows.append(("Contato Financeiro Cliente", data.contato_financeiro_cliente))
```

PARA:

```python
        # Valor (estruturado, com fallback legado)
        if data.valor_tipo == "percentual" and data.valor_percentual:
            rows.append(("Percentual", f"{data.valor_percentual}%"))
        elif data.valor_tipo == "valor" and data.valor_monetario is not None:
            rows.append(("Valor", f"R$ {data.valor_monetario:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))
        elif data.valor_tipo == "outro" and data.valor_outro:
            rows.append(("Critério", data.valor_outro))
        elif data.percentual_ou_valor:
            rows.append(("Percentual/Valor", data.percentual_ou_valor))
        # Para quem (lista)
        if data.para_quem:
            rows.append(("Para quem", ", ".join(data.para_quem)))
        if data.natureza:
            rows.append(("Natureza", data.natureza))
        if data.responsavel_captacao:
            rows.append(("Resp. Captação", data.responsavel_captacao))
        if data.responsavel_gestao:
            rows.append(("Resp. Gestão", data.responsavel_gestao))
        # Contato financeiro (3 campos, com fallback legado)
        if data.contato_financeiro_nome or data.contato_financeiro_email or data.contato_financeiro_telefone:
            if data.contato_financeiro_nome:
                rows.append(("Contato — Nome", data.contato_financeiro_nome))
            if data.contato_financeiro_email:
                rows.append(("Contato — E-mail", data.contato_financeiro_email))
            if data.contato_financeiro_telefone:
                rows.append(("Contato — Telefone", data.contato_financeiro_telefone))
        elif data.contato_financeiro_cliente:
            rows.append(("Contato Financeiro Cliente", data.contato_financeiro_cliente))
```

- [ ] **Step 5: Rodar testes**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/test_participacao_ficha.py tests/ --ignore=tests/integration -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/email.py backend/tests/test_participacao_ficha.py
git commit -m "feat(ficha): renderizar participacao estruturada com fallback legado"
```

---

## Task 4: Frontend — tipos + api (`listColaboradores`, `sendParticipacao`) + normalizeFormData

**Files:**
- Modify: `frontend/src/types/contract.ts` (interface `Participacao`)
- Modify: `frontend/src/app/lib/api.ts` (`sendParticipacao` + nova `listColaboradores`)
- Modify: `frontend/src/components/ContractWizard.tsx` (`normalizeFormData` participacao)

- [ ] **Step 1: Atualizar a interface `Participacao`**

Em `frontend/src/types/contract.ts`, substituir a interface `Participacao` por:

```ts
export type ParticipacaoValorTipo = "percentual" | "valor" | "outro";

export interface Participacao {
  tem_participacao: boolean;
  valor_tipo?: ParticipacaoValorTipo;
  valor_percentual?: string;
  valor_monetario?: number;
  valor_outro?: string;
  para_quem?: string[];
  natureza?: string;
  responsavel_captacao?: string;
  responsavel_gestao?: string;
  contato_financeiro_nome?: string;
  contato_financeiro_email?: string;
  contato_financeiro_telefone?: string;
  // legados (compat edição)
  percentual_ou_valor?: string;
  contato_financeiro_cliente?: string;
}
```

- [ ] **Step 2: Adicionar `listColaboradores` e atualizar `sendParticipacao` na api**

Em `frontend/src/app/lib/api.ts`, substituir a função `sendParticipacao` por:

```ts
export async function sendParticipacao(data: {
  contract_id: string;
  cliente_nome: string;
  objeto_contrato?: string;
  valor_tipo?: string;
  valor_percentual?: string;
  valor_monetario?: number;
  valor_outro?: string;
  para_quem?: string[];
  natureza?: string;
  responsavel_captacao?: string;
  responsavel_gestao?: string;
  contato_financeiro_nome?: string;
  contato_financeiro_email?: string;
  contato_financeiro_telefone?: string;
}) {
  return request<{ success: boolean; message: string }>("/api/email/send-participacao", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listColaboradores() {
  return request<{ colaboradores: Array<{ name: string; email: string; role: string }> }>(
    "/api/users/colaboradores"
  );
}
```

- [ ] **Step 3: Atualizar `normalizeFormData` (participacao)**

Em `frontend/src/components/ContractWizard.tsx`, no objeto retornado por `normalizeFormData`, substituir o bloco `participacao: { ... }` por (migra legado ao carregar contrato salvo):

```ts
    participacao: (() => {
      const p = data.participacao ?? {};
      const paraQuem = Array.isArray(p.para_quem)
        ? p.para_quem
        : typeof p.para_quem === "string" && p.para_quem.trim()
          ? [p.para_quem]
          : [];
      let valorTipo = p.valor_tipo;
      let valorOutro = p.valor_outro ?? "";
      if (!valorTipo && p.percentual_ou_valor) {
        valorTipo = "outro";
        valorOutro = p.percentual_ou_valor;
      }
      return {
        tem_participacao: p.tem_participacao ?? false,
        valor_tipo: valorTipo,
        valor_percentual: p.valor_percentual ?? "",
        valor_monetario: p.valor_monetario,
        valor_outro: valorOutro,
        para_quem: paraQuem,
        natureza: p.natureza ?? "",
        responsavel_captacao: p.responsavel_captacao ?? "",
        responsavel_gestao: p.responsavel_gestao ?? "",
        contato_financeiro_nome: p.contato_financeiro_nome ?? "",
        contato_financeiro_email: p.contato_financeiro_email ?? "",
        contato_financeiro_telefone: p.contato_financeiro_telefone ?? "",
      };
    })(),
```

> Nota TS: `data.participacao` é tipado como `Participacao`; como agora `para_quem` é `string[]`, o ramo `typeof p.para_quem === "string"` serve para dados legados vindos do backend (cast). Se o TS reclamar do `typeof string` em `string[]`, trate `p` como `any` localmente: `const p = (data.participacao ?? {}) as any;`.

- [ ] **Step 4: Build/typecheck**

Run (de `frontend/`): `npm run build`
Expected: sucesso. (Step5/Step7 ainda usam campos antigos — serão atualizados nas Tasks 5 e 6; se o build acusar erro de tipo em Step5/Step7 por `para_quem`/`percentual_ou_valor`, isso é esperado e resolvido nas próximas tasks. Para manter o build verde a cada task, execute as Tasks 4→5→6 em sequência e rode o build ao fim da Task 6; ainda assim rode aqui para ver o escopo dos erros.)

> Se preferir build verde a cada commit: nesta task, após editar, rode `npx tsc --noEmit` e anote os erros remanescentes em Step5/Step7 (esperados). Commit mesmo assim — Tasks 5 e 6 fecham.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/contract.ts frontend/src/app/lib/api.ts frontend/src/components/ContractWizard.tsx
git commit -m "feat(participacao): tipos + api colaboradores + normalize migracao"
```

---

## Task 5: Frontend — reescrever `Step5Participacao.tsx`

**Files:**
- Modify: `frontend/src/components/steps/Step5Participacao.tsx` (substituição completa)

- [ ] **Step 1: Substituir o arquivo inteiro**

Substituir TODO o conteúdo de `frontend/src/components/steps/Step5Participacao.tsx` por:

```tsx
"use client";

import { useEffect, useState } from "react";
import FormField, { Checkbox, Input, Select } from "@/components/ui/FormField";
import { Toggle } from "@/components/ui/FormField";
import CurrencyInput from "@/components/ui/CurrencyInput";
import type { EscopoItem, Participacao, ParticipacaoValorTipo } from "@/types/contract";
import { ESCOPO_LABELS } from "@/types/contract";
import { listColaboradores } from "@/app/lib/api";

function buildObjetoLines(escopos: EscopoItem[]): string[] {
  const lines: string[] = [];
  escopos.forEach((escopo) => {
    const label = ESCOPO_LABELS[escopo.tipo] || escopo.tipo;
    let detail = label;
    if (escopo.descricao_custom) detail += ` - ${escopo.descricao_custom}`;
    if (escopo.numero_autos) detail += ` | Autos: ${escopo.numero_autos}`;
    if (escopo.demandas) detail += ` | Demandas: ${escopo.demandas}`;
    if (escopo.pessoas_patrimonios) detail += ` | Pessoas/Patrimônios: ${escopo.pessoas_patrimonios}`;
    if (escopo.tipo_reestruturacao) detail += ` | Reestruturação: ${escopo.tipo_reestruturacao}`;
    if (escopo.documentos) detail += ` | Documentos: ${escopo.documentos}`;
    if (escopo.consulta) detail += ` | Consulta: ${escopo.consulta}`;
    if (escopo.subtipo_memoriais) {
      const a: string[] = [];
      if (escopo.subtipo_memoriais.elaboracao_memoriais) a.push("Elaboração de memoriais");
      if (escopo.subtipo_memoriais.despacho_memoriais) a.push("Despacho de memoriais");
      if (escopo.subtipo_memoriais.sustentacao_oral_relator) a.push("Sustentação oral (relator)");
      if (escopo.subtipo_memoriais.sustentacao_oral_todos_julgadores) a.push("Sustentação oral (todos julgadores)");
      if (a.length > 0) detail += ` | Atividades: ${a.join(", ")}`;
    }
    lines.push(detail);
  });
  return lines;
}

function maskTelefoneBR(value: string): string {
  const d = value.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d.length ? `(${d}` : "";
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

const VALOR_TIPOS: Array<{ value: ParticipacaoValorTipo; label: string }> = [
  { value: "percentual", label: "Percentual (%)" },
  { value: "valor", label: "Valor (R$)" },
  { value: "outro", label: "Outro critério" },
];

interface Step5Props {
  participacao: Participacao;
  onChange: (participacao: Participacao) => void;
  escopos: EscopoItem[];
}

export default function Step5Participacao({ participacao, onChange, escopos }: Step5Props) {
  const objetoLines = buildObjetoLines(escopos);
  const [colaboradores, setColaboradores] = useState<Array<{ name: string; email: string; role: string }>>([]);
  const [colabError, setColabError] = useState("");

  useEffect(() => {
    let active = true;
    listColaboradores()
      .then((res) => { if (active) setColaboradores(res.colaboradores); })
      .catch(() => { if (active) setColabError("Não foi possível carregar a lista de advogados."); });
    return () => { active = false; };
  }, []);

  const set = (partial: Partial<Participacao>) => onChange({ ...participacao, ...partial });

  const setValorTipo = (tipo: ParticipacaoValorTipo) =>
    set({ valor_tipo: tipo, valor_percentual: "", valor_monetario: undefined, valor_outro: "" });

  const toggleParaQuem = (nome: string, checked: boolean) => {
    const atual = participacao.para_quem ?? [];
    set({ para_quem: checked ? [...atual, nome] : atual.filter((n) => n !== nome) });
  };

  const nomeOptions = colaboradores.map((c) => ({ value: c.name, label: c.name }));

  return (
    <div>
      <h2 className="text-xl font-bold text-primary mb-2">5. Participações (Ficha Interna)</h2>
      <p className="text-sm text-muted mb-2">
        Informações internas sobre participação. O cliente <strong>não terá acesso</strong> a estes dados.
      </p>
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-6">
        <p className="text-xs text-yellow-800 font-medium">
          Atenção: Esta ficha é apenas para fins internos do escritório.
        </p>
      </div>

      {objetoLines.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <p className="text-sm font-semibold text-blue-900 mb-2">Objeto do Contrato</p>
          <ul className="list-disc list-inside space-y-1">
            {objetoLines.map((line, idx) => (
              <li key={idx} className="text-sm text-blue-800">{line}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <Toggle
          label="Este contrato terá participação?"
          value={participacao.tem_participacao}
          onChange={(v) => set({ tem_participacao: v })}
        />

        {participacao.tem_participacao && (
          <div className="space-y-6 mt-4">
            {/* Valor da participação */}
            <div>
              <p className="text-sm font-semibold text-foreground mb-2">Valor da participação</p>
              <div className="flex flex-wrap gap-4 mb-3">
                {VALOR_TIPOS.map((t) => (
                  <label key={t.value} className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="radio"
                      name="valor_tipo"
                      checked={participacao.valor_tipo === t.value}
                      onChange={() => setValorTipo(t.value)}
                      className="h-4 w-4 text-primary focus:ring-primary-light"
                    />
                    {t.label}
                  </label>
                ))}
              </div>

              {participacao.valor_tipo === "percentual" && (
                <FormField label="Percentual (%)">
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={participacao.valor_percentual ?? ""}
                    onChange={(e) => set({ valor_percentual: e.target.value })}
                    placeholder="Ex: 10"
                  />
                </FormField>
              )}

              {participacao.valor_tipo === "valor" && (
                <FormField label="Valor (R$)">
                  <CurrencyInput
                    value={participacao.valor_monetario}
                    onChange={(v) => set({ valor_monetario: v })}
                    placeholder="0,00"
                  />
                </FormField>
              )}

              {participacao.valor_tipo === "outro" && (
                <FormField label="Outro critério">
                  <Input
                    value={participacao.valor_outro ?? ""}
                    onChange={(e) => set({ valor_outro: e.target.value })}
                    placeholder="Descreva o critério da participação"
                  />
                </FormField>
              )}
            </div>

            {/* Para quem (multi advogados) */}
            <div>
              <p className="text-sm font-semibold text-foreground mb-2">Para quem?</p>
              {colabError && <p className="text-xs text-red-500 mb-2">{colabError}</p>}
              {colaboradores.length === 0 && !colabError && (
                <p className="text-xs text-muted">Nenhum colaborador encontrado.</p>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {colaboradores.map((c) => (
                  <Checkbox
                    key={c.email}
                    label={c.name}
                    checked={(participacao.para_quem ?? []).includes(c.name)}
                    onChange={(checked) => toggleParaQuem(c.name, checked)}
                  />
                ))}
              </div>
            </div>

            {/* Natureza + responsáveis */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField label="Natureza da participação">
                <Select
                  value={participacao.natureza || ""}
                  onChange={(e) => set({ natureza: e.target.value })}
                  placeholder="Selecione a natureza da participação"
                  options={[
                    { value: "Captação", label: "Captação" },
                    { value: "Performance", label: "Performance" },
                    { value: "Captação e performance", label: "Captação e performance" },
                    { value: "Projeto", label: "Projeto" },
                    { value: "Outro", label: "Outro" },
                  ]}
                />
              </FormField>

              <FormField label="Responsável pela captação">
                <Select
                  value={participacao.responsavel_captacao || ""}
                  onChange={(e) => set({ responsavel_captacao: e.target.value })}
                  placeholder="Selecione o advogado"
                  options={nomeOptions}
                />
              </FormField>

              <FormField label="Responsável pela gestão do contrato">
                <Select
                  value={participacao.responsavel_gestao || ""}
                  onChange={(e) => set({ responsavel_gestao: e.target.value })}
                  placeholder="Selecione o advogado"
                  options={nomeOptions}
                />
              </FormField>
            </div>

            {/* Contato financeiro do cliente (3 campos) */}
            <div>
              <p className="text-sm font-semibold text-foreground mb-2">
                Contato do responsável financeiro do cliente
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FormField label="Nome">
                  <Input
                    value={participacao.contato_financeiro_nome ?? ""}
                    onChange={(e) => set({ contato_financeiro_nome: e.target.value })}
                    placeholder="Nome"
                  />
                </FormField>
                <FormField label="E-mail">
                  <Input
                    type="email"
                    value={participacao.contato_financeiro_email ?? ""}
                    onChange={(e) => set({ contato_financeiro_email: e.target.value })}
                    placeholder="email@exemplo.com"
                  />
                </FormField>
                <FormField label="Telefone">
                  <Input
                    value={participacao.contato_financeiro_telefone ?? ""}
                    onChange={(e) => set({ contato_financeiro_telefone: maskTelefoneBR(e.target.value) })}
                    placeholder="(00) 00000-0000"
                  />
                </FormField>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build/typecheck**

Run (de `frontend/`): `npm run build`
Expected: compila (pode restar 1 erro em Step7 — resolvido na Task 6). Se quiser isolar: `npx tsc --noEmit` e confirmar que erros restantes são só em `Step7Envio.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/steps/Step5Participacao.tsx
git commit -m "feat(participacao): UI etapa 5 (radio valor, advogados, contato 3 campos)"
```

---

## Task 6: Frontend — `Step7Envio.tsx` envia campos novos

**Files:**
- Modify: `frontend/src/components/steps/Step7Envio.tsx` (as 2 chamadas `sendParticipacao`)

> Atenção: dependendo de qual branch estiver mesclado, este arquivo pode estar na versão de recipient único (master) ou multi (PR #34). A mudança abaixo é só nos ARGUMENTOS de `sendParticipacao`, que existem em ambas as versões — localize as chamadas e troque o objeto passado.

- [ ] **Step 1: Atualizar as chamadas `sendParticipacao`**

Em `frontend/src/components/steps/Step7Envio.tsx`, há duas chamadas a `sendParticipacao` (em `handleSubmit` e `handleSaveOnly`). Em AMBAS, substituir o objeto passado. Localize cada bloco:

```tsx
          await sendParticipacao({
            contract_id: resultContractId,
            cliente_nome: getContratanteNome(data.contratantes[0]),
            objeto_contrato: buildObjetoContrato(data.escopos),
            percentual_ou_valor: data.participacao.percentual_ou_valor || "",
            para_quem: data.participacao.para_quem || "",
            natureza: data.participacao.natureza || "",
            responsavel_captacao: data.participacao.responsavel_captacao || "",
            responsavel_gestao: data.participacao.responsavel_gestao || "",
            contato_financeiro_cliente: data.participacao.contato_financeiro_cliente || "",
          });
```

E substituir por:

```tsx
          await sendParticipacao({
            contract_id: resultContractId,
            cliente_nome: getContratanteNome(data.contratantes[0]),
            objeto_contrato: buildObjetoContrato(data.escopos),
            valor_tipo: data.participacao.valor_tipo,
            valor_percentual: data.participacao.valor_percentual,
            valor_monetario: data.participacao.valor_monetario,
            valor_outro: data.participacao.valor_outro,
            para_quem: data.participacao.para_quem ?? [],
            natureza: data.participacao.natureza,
            responsavel_captacao: data.participacao.responsavel_captacao,
            responsavel_gestao: data.participacao.responsavel_gestao,
            contato_financeiro_nome: data.participacao.contato_financeiro_nome,
            contato_financeiro_email: data.participacao.contato_financeiro_email,
            contato_financeiro_telefone: data.participacao.contato_financeiro_telefone,
          });
```

(Há duas ocorrências idênticas — aplicar nas duas.)

- [ ] **Step 2: Build/typecheck (agora deve ficar verde)**

Run (de `frontend/`): `npm run build`
Expected: sucesso, sem erros de tipo.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/steps/Step7Envio.tsx
git commit -m "feat(envio): enviar campos de participacao estruturados na ficha"
```

---

## Self-Review (autor do plano)

- **Cobertura do spec:**
  - Endpoint colaboradores não-admin → Task 1.
  - Radio valor (percentual/valor/outro) + validações → Task 5 (UI) + Task 2/3 (modelo/ficha).
  - Para quem multi (checkboxes) → Task 5; storage list[str] → Task 2/3; api array → Task 4.
  - Responsáveis dropdown único → Task 5.
  - Contato 3 campos + máscara telefone → Task 5; storage/ficha → Task 2/3.
  - Migração contratos antigos → Task 2 (backend validator) + Task 4 (normalizeFormData).
  - Ficha financeiro reflete novos campos → Task 3.
  - build/testes → Tasks 1/2/3 pytest, Task 6 build verde final.
- **Placeholders:** nenhum; todo passo mostra código real.
- **Consistência de tipos:** `valor_tipo`/`valor_percentual`/`valor_monetario`(number/float)/`valor_outro`, `para_quem: string[]`, `contato_financeiro_nome|email|telefone`, `ParticipacaoValorTipo` — usados igual em types, api, model, ficha, Step5, Step7.
- **Nota de ordem:** o build só fica 100% verde ao fim da Task 6 (Tasks 4→5→6 são acopladas pela mudança de tipo `para_quem`/valor). Cada uma commita; build final na Task 6. Backend (1/2/3) é independente e verde a cada task.
