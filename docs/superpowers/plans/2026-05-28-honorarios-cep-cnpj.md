# Honorários (datas em calendário) + CEP/CNPJ (revelação progressiva) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Honorários usam só calendário (sem texto livre de vencimento); endereço (CEP) e Razão Social/Endereço (CNPJ) só aparecem após o lookup e ficam read-only.

**Architecture:** Mudanças em 2 componentes React do wizard (`Step1Contratante.tsx`, `Step3Honorarios.tsx`) + 1 ajuste no gerador de contrato Python (`contract_generator.py`). Revelação progressiva via condicional de render; campos auto-preenchidos viram `readOnly`. Backend formata vencimento recorrente como "todo dia DD".

**Tech Stack:** Next.js 15 / React 19 / TypeScript / Tailwind (frontend, sem framework de teste de componente — verificação por `npm run build`); FastAPI / Pydantic / pytest (backend).

**Diretório de trabalho:** todas as paths são relativas a `C:/Users/paollo/Downloads/Codigo/Honorario-cf`. Commits no repo git desse diretório (branch atual `feature/dates-honorarios`).

---

## Task 1: Backend — vencimento recorrente vira "todo dia DD"

**Files:**
- Modify: `backend/app/services/contract_generator.py` (método `_vencimento_combined`, ~linha 310-322)
- Test: `backend/tests/test_vencimento_recorrente.py` (criar)

Comando de teste roda do diretório `backend/` com o venv do projeto:
`C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest <arquivo> -v`

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_vencimento_recorrente.py`:

```python
"""Vencimento recorrente com data de calendário deve render 'todo dia DD'."""
from app.services.contract_generator import ContractGenerator


def test_recorrente_com_data_usa_todo_dia():
    g = ContractGenerator()
    assert g._vencimento_combined("2026-01-05", None, None, recorrente=True) == "todo dia 05"


def test_nao_recorrente_com_data_mantem_em_data():
    g = ContractGenerator()
    assert g._vencimento_combined("2026-01-05", None, None, recorrente=False) == "em 05/01/2026"


def test_recorrente_com_data_e_obs_concatena():
    g = ContractGenerator()
    assert (
        g._vencimento_combined("2026-01-05", "ajustável", None, recorrente=True)
        == "todo dia 05 (ajustável)"
    )


def test_recorrente_sem_data_sem_obs_cai_no_legacy():
    g = ContractGenerator()
    # legacy "5" + recorrente segue o formato existente de _format_vencimento (inalterado)
    out = g._vencimento_combined(None, None, "5", recorrente=True)
    assert out != "todo dia 05"  # caminho legacy não muda; só garante que não quebrou
    assert out  # retorna algo não-vazio
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/test_vencimento_recorrente.py -v`
Expected: `test_recorrente_com_data_usa_todo_dia` e `test_recorrente_com_data_e_obs_concatena` FALHAM (retornam "em 05/01/2026" / "em 05/01/2026 (ajustável)").

- [ ] **Step 3: Implementar a mudança mínima**

Em `backend/app/services/contract_generator.py`, no método `_vencimento_combined`, trocar o bloco que monta `base`:

DE:
```python
        if data:
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(data)
                base = f"em {dt.day:02d}/{dt.month:02d}/{dt.year}"
            except Exception:
                base = self._format_vencimento(data, recorrente=recorrente)
```

PARA:
```python
        if data:
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(data)
                if recorrente:
                    base = f"todo dia {dt.day:02d}"
                else:
                    base = f"em {dt.day:02d}/{dt.month:02d}/{dt.year}"
            except Exception:
                base = self._format_vencimento(data, recorrente=recorrente)
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/test_vencimento_recorrente.py -v`
Expected: 4 passed.

- [ ] **Step 5: Rodar a suíte backend para garantir que nada quebrou**

Run: `C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest tests/ --ignore=tests/integration -q`
Expected: tudo passando (ou só os pré-existentes que já falhavam antes da mudança; nenhum novo erro relacionado a vencimento).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/contract_generator.py backend/tests/test_vencimento_recorrente.py
git commit -m "feat(contrato): vencimento recorrente renderiza 'todo dia DD'"
```

---

## Task 2: Frontend — remover textos livres de "Observação" de vencimento (Step3)

**Files:**
- Modify: `frontend/src/components/steps/Step3Honorarios.tsx`

São 4 blocos `<FormField label="Observação" ...>` (e um "Observação parcelas") ligados a campos `*_obs`. Remover apenas esses blocos JSX; manter os `DatePicker`. Não mexer nos tipos TS.

- [ ] **Step 1: Remover obs do Pró-labore (vencimento à vista)**

Em `frontend/src/components/steps/Step3Honorarios.tsx`, dentro do bloco Pró-labore (`!escopo.pro_labore.tem_parcelamento`), remover este JSX:

```tsx
                          <FormField
                            label="Observação"
                            hint="Opcional: regra ou condição de vencimento."
                          >
                            <Input
                              value={escopo.pro_labore.vencimento_obs || ""}
                              onChange={(e) =>
                                updateProLabore(idx, { vencimento_obs: e.target.value })
                              }
                              placeholder="Ex: após assinatura"
                            />
                          </FormField>
```

- [ ] **Step 2: Remover obs das parcelas do Pró-labore**

No mesmo arquivo, dentro do bloco `escopo.pro_labore.tem_parcelamento`, remover:

```tsx
                          <FormField
                            label="Observação parcelas"
                            hint="Opcional: dia mensal ou regra (ex: 'todo dia 5')."
                          >
                            <Input
                              value={escopo.pro_labore.vencimento_parcelas_obs || ""}
                              onChange={(e) =>
                                updateProLabore(idx, { vencimento_parcelas_obs: e.target.value })
                              }
                              placeholder="Ex: todo dia 5"
                            />
                          </FormField>
```

- [ ] **Step 3: Remover obs da Mensalidade**

No bloco Mensalidade, remover:

```tsx
                      <FormField
                        label="Observação"
                        hint="Opcional: dia mensal recorrente (ex.: 5) ou regra."
                      >
                        <Input
                          value={escopo.mensalidade.dia_vencimento_obs || ""}
                          onChange={(e) =>
                            updateMensalidade(idx, { dia_vencimento_obs: e.target.value })
                          }
                          placeholder="Ex: todo dia 5"
                        />
                      </FormField>
```

- [ ] **Step 4: Remover obs do Êxito**

No bloco Êxito, remover:

```tsx
                      <FormField
                        label="Observação"
                        hint="Opcional: prazo ou condição (ex: 'em até 5 dias após o benefício')."
                      >
                        <Input
                          value={escopo.exito.vencimento_obs || ""}
                          onChange={(e) =>
                            updateExito(idx, { vencimento_obs: e.target.value })
                          }
                          placeholder="Ex: em até 5 dias após o benefício"
                        />
                      </FormField>
```

- [ ] **Step 5: Verificar build/typecheck**

Run (do diretório `frontend/`): `npm run build`
Expected: build sucesso. `Input` ainda é usado em outros campos do arquivo, então o import não fica órfão (se o lint reclamar de import não usado, conferir — neste arquivo `Input` segue em uso em "Horas no pacote", "Número de parcelas", etc., então OK).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/steps/Step3Honorarios.tsx
git commit -m "feat(honorarios): remover textos livres de vencimento, manter so calendario"
```

---

## Task 3: Frontend — CEP revelação progressiva + endereço read-only (PFForm)

**Files:**
- Modify: `frontend/src/components/steps/Step1Contratante.tsx` (função `PFForm`, ~linha 371-527)

Regra: Número, Complemento e "Endereço completo" ficam ocultos até `cepData != null`. Em edição (contrato salvo) o "Endereço completo" deve reaparecer mesmo sem novo lookup, lendo `data.endereco`. Endereço completo vira `readOnly`.

- [ ] **Step 1: Calcular flags de revelação no topo do PFForm**

Em `frontend/src/components/steps/Step1Contratante.tsx`, dentro de `PFForm`, logo após a linha `const handleComplementoChange = ...` (antes do `return (`), adicionar:

```tsx
  const enderecoRevelado = cepData != null || (data.endereco?.trim().length ?? 0) > 0;
```

- [ ] **Step 2: Esconder Número e Complemento até o CEP**

Substituir os dois `<FormField>` de Número e Complemento (que hoje usam `disabled={!cepData}`):

DE:
```tsx
      <FormField label="Número">
        <Input
          value={numero}
          onChange={(e) => handleNumeroChange(e.target.value)}
          placeholder="Ex: 271"
          disabled={!cepData}
        />
      </FormField>

      <FormField label="Complemento">
        <Input
          value={complemento}
          onChange={(e) => handleComplementoChange(e.target.value)}
          placeholder="Apto, sala, bloco..."
          disabled={!cepData}
        />
      </FormField>
```

PARA:
```tsx
      {cepData && (
        <FormField label="Número">
          <Input
            value={numero}
            onChange={(e) => handleNumeroChange(e.target.value)}
            placeholder="Ex: 271"
          />
        </FormField>
      )}

      {cepData && (
        <FormField label="Complemento">
          <Input
            value={complemento}
            onChange={(e) => handleComplementoChange(e.target.value)}
            placeholder="Apto, sala, bloco..."
          />
        </FormField>
      )}
```

- [ ] **Step 3: Esconder Endereço completo até revelado e torná-lo read-only**

Substituir o `<FormField label="Endereço completo" required>`:

DE:
```tsx
      <FormField label="Endereço completo" required>
        <Input
          value={data.endereco}
          onChange={(e) => onUpdate({ endereco: e.target.value })}
          placeholder="Rua, número, bairro, cidade/UF, CEP"
          required
        />
      </FormField>
```

PARA:
```tsx
      {enderecoRevelado && (
        <FormField label="Endereço completo" required>
          <Input
            value={data.endereco}
            readOnly
            placeholder="Preenchido automaticamente pelo CEP"
            className="bg-gray-50 cursor-not-allowed"
            required
          />
        </FormField>
      )}
```

- [ ] **Step 4: Verificar build/typecheck**

Run (do diretório `frontend/`): `npm run build`
Expected: build sucesso.

- [ ] **Step 5: Verificação manual rápida (smoke)**

Run (do diretório `frontend/`): `npm run dev`, abrir o wizard, etapa 1, tipo Pessoa Física.
Expected: sem CEP, só aparecem Nome/CPF/Nacionalidade/Profissão/Estado Civil/E-mail/CEP. Ao digitar um CEP válido (ex: 30130-000), aparecem Número, Complemento e Endereço completo; o Endereço completo é cinza e não editável.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/steps/Step1Contratante.tsx
git commit -m "feat(cep): ocultar endereco ate CEP e travar endereco completo"
```

---

## Task 4: Frontend — CNPJ revelação progressiva + read-only (PJForm)

**Files:**
- Modify: `frontend/src/components/steps/Step1Contratante.tsx` (componente `Step1Contratante` + função `PJForm`)

Regra: Razão Social e Endereço só aparecem após o lookup do CNPJ ter sucesso, e ficam `readOnly`. Em edição (contrato com `razao_social` já preenchida), considerar revelado. Checkbox "Adicionar representante" continua **sempre visível**. Precisamos de uma flag de sucesso (hoje só existe loading/erro).

- [ ] **Step 1: Adicionar estado de sucesso do lookup no Step1Contratante**

Em `frontend/src/components/steps/Step1Contratante.tsx`, no componente `Step1Contratante`, ao lado de `const [loadingCNPJ, setLoadingCNPJ] = useState<number | null>(null);`, adicionar:

```tsx
  const [cnpjLoaded, setCnpjLoaded] = useState<Set<number>>(new Set());
```

- [ ] **Step 2: Marcar como carregado no sucesso do lookup**

No `handleCNPJLookup`, dentro do `try`, logo após o `updateContratante(index, { razao_social: ..., endereco: ... })`, adicionar a marcação de sucesso:

DE:
```tsx
        const data = await lookupCNPJ(cnpj);
        updateContratante(index, {
          razao_social: data.razao_social,
          endereco: data.endereco,
        });
```

PARA:
```tsx
        const data = await lookupCNPJ(cnpj);
        updateContratante(index, {
          razao_social: data.razao_social,
          endereco: data.endereco,
        });
        setCnpjLoaded((prev) => new Set(prev).add(index));
```

- [ ] **Step 3: Passar a flag `loaded` para o PJForm**

Onde o `PJForm` é renderizado (dentro do map de contratantes), adicionar a prop `loaded`. A flag é verdadeira se o lookup foi feito nesta sessão OU se o contratante já vem com `razao_social` preenchida (caso de edição):

DE:
```tsx
            <PJForm
              data={c}
              index={idx}
              loadingCNPJ={loadingCNPJ === idx}
              onUpdate={(partial) => updateContratante(idx, partial)}
              onCNPJLookup={(cnpj) => handleCNPJLookup(idx, cnpj)}
            />
```

PARA:
```tsx
            <PJForm
              data={c}
              index={idx}
              loadingCNPJ={loadingCNPJ === idx}
              loaded={cnpjLoaded.has(idx) || (c.tipo === "PJ" && !!c.razao_social)}
              onUpdate={(partial) => updateContratante(idx, partial)}
              onCNPJLookup={(cnpj) => handleCNPJLookup(idx, cnpj)}
            />
```

- [ ] **Step 4: Adicionar `loaded` à assinatura do PJForm**

Na definição de `PJForm`, adicionar `loaded` aos props:

DE:
```tsx
function PJForm({
  data,
  index,
  loadingCNPJ,
  onUpdate,
  onCNPJLookup,
}: {
  data: ContratantePJ;
  index: number;
  loadingCNPJ: boolean;
  onUpdate: (partial: Partial<ContratantePJ>) => void;
  onCNPJLookup: (cnpj: string) => void;
}) {
```

PARA:
```tsx
function PJForm({
  data,
  index,
  loadingCNPJ,
  loaded,
  onUpdate,
  onCNPJLookup,
}: {
  data: ContratantePJ;
  index: number;
  loadingCNPJ: boolean;
  loaded: boolean;
  onUpdate: (partial: Partial<ContratantePJ>) => void;
  onCNPJLookup: (cnpj: string) => void;
}) {
```

> Nota: `index` pode aparecer como não usado pelo lint. Já era passado antes desta mudança; se o lint acusar `index` não usado e bloquear o build, prefixar com underscore na desestruturação (`index: _index`) — mas só fazer isso se o build falhar por causa disso.

- [ ] **Step 5: Ocultar Razão Social e Endereço até `loaded` e torná-los read-only**

Substituir os dois `<FormField>` de Razão Social e Endereço no PJForm:

DE:
```tsx
      <FormField label="Razão Social">
        <Input
          value={data.razao_social}
          onChange={(e) => onUpdate({ razao_social: e.target.value })}
          placeholder="Preenchido automaticamente pelo CNPJ"
        />
      </FormField>

      <FormField label="Endereço">
        <Input
          value={data.endereco}
          onChange={(e) => onUpdate({ endereco: e.target.value })}
          placeholder="Preenchido automaticamente pelo CNPJ"
        />
      </FormField>
```

PARA:
```tsx
      {loaded && (
        <FormField label="Razão Social">
          <Input
            value={data.razao_social}
            readOnly
            placeholder="Preenchido automaticamente pelo CNPJ"
            className="bg-gray-50 cursor-not-allowed"
          />
        </FormField>
      )}

      {loaded && (
        <FormField label="Endereço">
          <Input
            value={data.endereco}
            readOnly
            placeholder="Preenchido automaticamente pelo CNPJ"
            className="bg-gray-50 cursor-not-allowed"
          />
        </FormField>
      )}
```

> O bloco `<div className="md:col-span-2">` com o `Checkbox` "Adicionar dados do representante legal" e o bloco do representante NÃO mudam — permanecem sempre visíveis.

- [ ] **Step 6: Verificar build/typecheck**

Run (do diretório `frontend/`): `npm run build`
Expected: build sucesso.

- [ ] **Step 7: Verificação manual rápida (smoke)**

Run (do diretório `frontend/`): `npm run dev`, etapa 1, tipo Pessoa Jurídica.
Expected: antes do lookup só aparecem CNPJ, E-mail e o checkbox de representante. Após "Buscar" com CNPJ válido, aparecem Razão Social e Endereço, ambos cinza e não editáveis.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/steps/Step1Contratante.tsx
git commit -m "feat(cnpj): revelar Razao Social/Endereco apos lookup e travar campos"
```

---

## Self-Review (preenchido pelo autor do plano)

- **Cobertura do spec:**
  - Parte A (remover obs honorários) → Task 2.
  - Parte B (backend "todo dia DD") → Task 1.
  - Parte C (CEP progressivo + endereço read-only) → Task 3.
  - Parte D (CNPJ progressivo + read-only, representante sempre visível, flag de sucesso, pré-fill em edição) → Task 4.
  - Critério 5 (edição mantém dados salvos) → Task 3 Step 1 (`enderecoRevelado` via `data.endereco`) e Task 4 Step 3 (`loaded` via `c.razao_social`).
  - Critério 6 (build + testes) → Task 1 Step 5, Tasks 2/3/4 `npm run build`.
- **Placeholders:** nenhum TBD/TODO; todo passo de código mostra o código.
- **Consistência de tipos:** prop `loaded: boolean` definida na assinatura do PJForm (Task 4 Step 4) e passada na renderização (Step 3); estado `cnpjLoaded: Set<number>` usado de forma consistente; `enderecoRevelado` é local do PFForm.
