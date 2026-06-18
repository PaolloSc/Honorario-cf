# Participação: base por Escopo ou Honorário — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar à etapa de Participação a escolha obrigatória de uma base (um Escopo ou um par Escopo+Honorário), travando o restante dos campos até a base ser selecionada, e exibir a base na revisão e no e-mail.

**Architecture:** Campos opcionais novos no model `Participacao` (front + back). UI no Step5 com radio de base + lista de seleção única; o restante do formulário só renderiza após `base_label` preenchido. Envio inclui os campos; revisão e e-mail exibem a base.

**Tech Stack:** Next.js/React/TypeScript (frontend); FastAPI/Pydantic + pytest (backend).

**Spec (fonte da verdade):** `docs/superpowers/specs/2026-05-29-participacao-base-escopo-honorario-design.md`

---

## File Structure

- Modify: `frontend/src/types/contract.ts` (campos em `Participacao` + `HONORARIO_LABELS`)
- Modify: `backend/app/models/contract.py` (`Participacao`)
- Modify: `backend/app/routers/email.py` (`ParticipacaoEmailRequest` + linha "Base")
- Modify: `frontend/src/components/steps/Step5Participacao.tsx` (UI base + gate)
- Modify: `frontend/src/app/lib/api.ts` (tipo `sendParticipacao`)
- Modify: `frontend/src/components/steps/Step7Envio.tsx` (2 chamadas `sendParticipacao`)
- Modify: `frontend/src/components/steps/Step6Revisao.tsx` (exibir base)
- Test: `backend/tests/test_participacao_base.py` (novo)

---

## Task 1: Tipos no frontend + HONORARIO_LABELS

**Files:**
- Modify: `frontend/src/types/contract.ts`

- [ ] **Step 1: Adicionar `HONORARIO_LABELS` após o bloco `TipoHonorario`**

No `frontend/src/types/contract.ts`, logo após o `export type TipoHonorario = ...` (atual L83–88), adicionar:

```ts
export const HONORARIO_LABELS: Record<TipoHonorario, string> = {
  hora_trabalhada: "Hora Trabalhada",
  pro_labore: "Pró-labore",
  mensalidade: "Mensalidade",
  exito: "Êxito",
  permuta: "Permuta",
};
```

- [ ] **Step 2: Adicionar campos de base em `Participacao`**

No `interface Participacao` (atual L216–232), adicionar antes do comentário `// legados`:

```ts
  base_tipo?: "escopo" | "honorario";
  base_escopo_index?: number;
  base_honorario?: TipoHonorario;
  base_label?: string;
```

- [ ] **Step 3: Verificar typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/contract.ts
git commit -m "feat(participacao): tipos base (escopo/honorario) + HONORARIO_LABELS"
```

---

## Task 2: Campos de base no model backend

**Files:**
- Modify: `backend/app/models/contract.py` (`Participacao`)
- Test: `backend/tests/test_participacao_base.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_participacao_base.py
"""Participacao: campos de base (escopo/honorario)."""
from app.models.contract import Participacao


def test_base_fields_aceitos():
    p = Participacao(
        tem_participacao=True,
        base_tipo="honorario",
        base_escopo_index=0,
        base_honorario="mensalidade",
        base_label="Consultoria LGPD · Mensalidade",
    )
    assert p.base_tipo == "honorario"
    assert p.base_escopo_index == 0
    assert p.base_honorario == "mensalidade"
    assert p.base_label == "Consultoria LGPD · Mensalidade"


def test_base_fields_opcionais_legado():
    # contrato antigo sem base continua valido
    p = Participacao(tem_participacao=True)
    assert p.base_tipo is None
    assert p.base_escopo_index is None
    assert p.base_label is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_participacao_base.py -v`
Expected: FAIL (campos `base_*` não existem).

- [ ] **Step 3: Adicionar campos em `Participacao`**

No `backend/app/models/contract.py`, dentro de `class Participacao` (atual L221–239),
adicionar antes do comentário `# Legados`:

```python
    # Base da participacao (escopo ou honorario)
    base_tipo: Optional[str] = None  # "escopo" | "honorario"
    base_escopo_index: Optional[int] = None
    base_honorario: Optional[str] = None
    base_label: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_participacao_base.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/contract.py backend/tests/test_participacao_base.py
git commit -m "feat(participacao): campos base no model (back)"
```

---

## Task 3: Email — schema + linha "Base"

**Files:**
- Modify: `backend/app/routers/email.py`
- Test: `backend/tests/test_participacao_base.py`

- [ ] **Step 1: Write the failing test**

```python
def test_email_request_aceita_base():
    from app.routers.email import ParticipacaoEmailRequest
    r = ParticipacaoEmailRequest(
        contract_id="x", cliente_nome="Fulano",
        base_tipo="escopo", base_label="Consultoria LGPD",
    )
    assert r.base_tipo == "escopo"
    assert r.base_label == "Consultoria LGPD"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_participacao_base.py::test_email_request_aceita_base -v`
Expected: FAIL (campos ausentes).

- [ ] **Step 3: Adicionar campos no schema `ParticipacaoEmailRequest`**

No `backend/app/routers/email.py`, em `class ParticipacaoEmailRequest`
(atual L31–51), adicionar antes do comentário `# Legados` (L49):

```python
    # Base da participacao
    base_tipo: str = ""
    base_escopo_index: int | None = None
    base_honorario: str = ""
    base_label: str = ""
```

- [ ] **Step 4: Adicionar linha "Base" no topo de `rows`**

No `backend/app/routers/email.py`, no bloco que monta `rows`
(atual L308–312), logo após a linha do "Objeto do Contrato" e antes do
bloco de Valor, inserir:

```python
        # Base da participacao (escopo ou honorario)
        if data.base_tipo and data.base_label:
            base_prefixo = "Escopo" if data.base_tipo == "escopo" else "Honorário"
            rows.append(("Base", f"{base_prefixo} — {data.base_label}"))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_participacao_base.py -v`
Expected: PASS (todos).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/email.py backend/tests/test_participacao_base.py
git commit -m "feat(participacao): email aceita base e exibe linha 'Base'"
```

---

## Task 4: UI Step5 — seleção de base + gate

**Files:**
- Modify: `frontend/src/components/steps/Step5Participacao.tsx`

- [ ] **Step 1: Importar `HONORARIO_LABELS` e `TipoHonorario`**

No topo de `Step5Participacao.tsx`, na linha de import de tipos (atual L6–7):

```tsx
import type { EscopoItem, Participacao, ParticipacaoValorTipo, TipoHonorario } from "@/types/contract";
import { ESCOPO_LABELS, HONORARIO_LABELS } from "@/types/contract";
```

- [ ] **Step 2: Adicionar helpers e handlers dentro do componente**

Dentro de `Step5Participacao`, logo após `const set = (partial...) => ...`
(atual L70), adicionar:

```tsx
  const escopoLabel = (e: EscopoItem) =>
    (ESCOPO_LABELS[e.tipo] || e.tipo) + (e.descricao_custom ? ` - ${e.descricao_custom}` : "");

  const setBaseTipo = (tipo: "escopo" | "honorario") =>
    set({ base_tipo: tipo, base_escopo_index: undefined, base_honorario: undefined, base_label: "" });

  const selecionarEscopo = (idx: number) =>
    set({ base_escopo_index: idx, base_honorario: undefined, base_label: escopoLabel(escopos[idx]) });

  const selecionarHonorario = (idx: number, hon: TipoHonorario) =>
    set({
      base_escopo_index: idx,
      base_honorario: hon,
      base_label: `${escopoLabel(escopos[idx])} · ${HONORARIO_LABELS[hon]}`,
    });

  // pares escopo+honorario para a lista de base por honorario
  const paresHonorario: Array<{ idx: number; hon: TipoHonorario; label: string }> = [];
  escopos.forEach((e, idx) => {
    (e.honorarios ?? []).forEach((hon) => {
      paresHonorario.push({ idx, hon, label: `${escopoLabel(e)} — ${HONORARIO_LABELS[hon]}` });
    });
  });

  const baseSelecionada = Boolean(participacao.base_label);
```

- [ ] **Step 3: Inserir o bloco de base e travar o restante**

Localizar o bloco condicional do conteúdo (atual L120–121):

```tsx
        {participacao.tem_participacao && (
          <div className="space-y-6 mt-4">
```

Substituir por (insere a seleção de base; o restante vira gated por `baseSelecionada`):

```tsx
        {participacao.tem_participacao && (
          <div className="space-y-6 mt-4">
            {/* Base da participação */}
            <div>
              <p className="text-sm font-semibold text-foreground mb-2">Base da participação</p>
              {escopos.length === 0 ? (
                <p className="text-xs text-muted">Defina escopos na etapa 2 primeiro.</p>
              ) : (
                <>
                  <div className="flex flex-wrap gap-4 mb-3">
                    {(["escopo", "honorario"] as const).map((t) => (
                      <label key={t} className="flex items-center gap-2 cursor-pointer text-sm">
                        <input
                          type="radio"
                          name="base_tipo"
                          checked={participacao.base_tipo === t}
                          onChange={() => setBaseTipo(t)}
                          className="h-4 w-4 text-primary focus:ring-primary-light"
                        />
                        {t === "escopo" ? "Escopo" : "Honorário"}
                      </label>
                    ))}
                  </div>

                  {participacao.base_tipo === "escopo" && (
                    <div className="space-y-2">
                      {escopos.map((e, idx) => (
                        <label key={idx} className="flex items-start gap-2 cursor-pointer text-sm">
                          <input
                            type="radio"
                            name="base_escopo"
                            checked={participacao.base_escopo_index === idx && !participacao.base_honorario}
                            onChange={() => selecionarEscopo(idx)}
                            className="h-4 w-4 mt-0.5 text-primary focus:ring-primary-light"
                          />
                          {escopoLabel(e)}
                        </label>
                      ))}
                    </div>
                  )}

                  {participacao.base_tipo === "honorario" && (
                    <div className="space-y-2">
                      {paresHonorario.length === 0 && (
                        <p className="text-xs text-muted">Nenhum honorário definido nos escopos.</p>
                      )}
                      {paresHonorario.map((p) => (
                        <label key={`${p.idx}-${p.hon}`} className="flex items-start gap-2 cursor-pointer text-sm">
                          <input
                            type="radio"
                            name="base_honorario"
                            checked={participacao.base_escopo_index === p.idx && participacao.base_honorario === p.hon}
                            onChange={() => selecionarHonorario(p.idx, p.hon)}
                            className="h-4 w-4 mt-0.5 text-primary focus:ring-primary-light"
                          />
                          {p.label}
                        </label>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {baseSelecionada && (
              <>
```

- [ ] **Step 4: Fechar o fragmento do gate antes do fim do bloco**

Localizar o fim do conteúdo (atual L260–262):

```tsx
            </div>
          </div>
        )}
```

Substituir por (fecha o `<> ... </>` do gate):

```tsx
            </div>
              </>
            )}
          </div>
        )}
```

> Atenção: o `</div>` da L260 fecha o bloco "Contato financeiro"; o `</>` novo
> fecha o fragmento aberto no Step 3; o `</div>` seguinte fecha o
> `space-y-6 mt-4`.

- [ ] **Step 5: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK, sem erros de TS/JSX.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/steps/Step5Participacao.tsx
git commit -m "feat(participacao): UI selecao de base (escopo/honorario) + trava restante"
```

---

## Task 5: Envio (api.ts + Step7) + Revisão (Step6)

**Files:**
- Modify: `frontend/src/app/lib/api.ts`
- Modify: `frontend/src/components/steps/Step7Envio.tsx`
- Modify: `frontend/src/components/steps/Step6Revisao.tsx`

- [ ] **Step 1: Adicionar campos no tipo `sendParticipacao`**

No `frontend/src/app/lib/api.ts`, no objeto do tipo `sendParticipacao`
(atual L131–146), adicionar antes do `}`:

```ts
  base_tipo?: string;
  base_escopo_index?: number;
  base_honorario?: string;
  base_label?: string;
```

- [ ] **Step 2: Incluir base nas DUAS chamadas `sendParticipacao` do Step7**

No `frontend/src/components/steps/Step7Envio.tsx` há duas chamadas
`sendParticipacao({ ... })` (uma ~L125, outra ~L184). Em **cada uma**, após a
linha `contato_financeiro_telefone: data.participacao.contato_financeiro_telefone,`
adicionar:

```tsx
            base_tipo: data.participacao.base_tipo,
            base_escopo_index: data.participacao.base_escopo_index,
            base_honorario: data.participacao.base_honorario,
            base_label: data.participacao.base_label,
```

- [ ] **Step 3: Exibir a base na revisão (Step6)**

No `frontend/src/components/steps/Step6Revisao.tsx`, dentro do `<ul>` da
participação (atual L126), como **primeiro** `<li>`, adicionar:

```tsx
            {data.participacao.base_label && (
              <li>
                Base: {data.participacao.base_tipo === "escopo" ? "Escopo" : "Honorário"} — {data.participacao.base_label}
              </li>
            )}
```

- [ ] **Step 4: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/lib/api.ts frontend/src/components/steps/Step7Envio.tsx frontend/src/components/steps/Step6Revisao.tsx
git commit -m "feat(participacao): enviar base no payload + exibir base na revisao"
```

---

## Self-Review (preenchido pelo autor do plano)

- **Cobertura do spec:** modelo de dados → Tasks 1,2; UI base + gate → Task 4;
  exibição revisão+email → Tasks 3,5; envio/persistência → Tasks 2,3,5;
  sem escopos → Task 4 (mensagem). ✅
- **Placeholders:** nenhum — todo código inline. ✅
- **Consistência de tipos:** `base_tipo`/`base_escopo_index`/`base_honorario`/
  `base_label` idênticos em `contract.ts`, `contract.py`, `ParticipacaoEmailRequest`,
  `sendParticipacao` e Step7. `base_label` gate consistente Step4↔Step5. ✅
- **Nota de execução:** Task 4 Steps 3–4 mexem em estrutura JSX aninhada —
  conferir o balanceamento de tags ao aplicar (o build do Step 5 valida).
