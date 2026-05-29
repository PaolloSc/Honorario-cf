# Participação — campos estruturados (tipo de valor, advogados, contato)

**Data:** 2026-05-29
**Status:** Aprovado (design)
**Branch:** feature/participacao-estruturada (base: master)

## Objetivo

Reformular a etapa 5 (Participações — ficha interna) do wizard de contrato:

1. **Valor da participação:** trocar o campo único de texto por seleção de UM tipo (radio): **Percentual** (número 0–100 + %), **Valor** (R$, só números), **Outro critério** (texto livre). Só o campo do tipo escolhido aparece.
2. **Para quem:** selecionar **vários** advogados (checkboxes com nome completo) em vez de texto livre.
3. **Responsável pela captação** e **Responsável pela gestão:** selecionar **um** advogado cada (dropdown).
4. **Contato do responsável financeiro do cliente:** separar em 3 campos — **Nome**, **E-mail**, **Telefone** (máscara BR `(00) 00000-0000`).

Lista de advogados = todos os usuários cadastrados. Armazenamento estruturado no backend, com migração compatível para contratos já salvos.

## Restrição descoberta

`GET /api/users` exige `require_admin` — o advogado no wizard não pode listá-lo. É necessário um endpoint não-admin para popular as seleções.

## Contexto

- Os campos de participação são **ficha interna**: enviados ao financeiro via `POST /api/email/send-participacao` (tabela de e-mail). NÃO entram no .docx (`contract_generator` importa `Participacao` mas não renderiza esses campos). `participation_calculator.py` é módulo separado do financeiro e não parseia esses campos.
- `validateParticipacao` retorna `[]` (participação é opcional). Mantemos opcional — sem novas validações bloqueantes.

## Escopo

**Backend:**
- `app/routers/users.py` — novo endpoint.
- `app/models/contract.py` — `Participacao` com campos novos + validator de migração.
- `app/routers/email.py` — `ParticipacaoEmailRequest` + montagem das linhas da ficha.

**Frontend:**
- `src/types/contract.ts` — espelhar campos.
- `src/app/lib/api.ts` — `listColaboradores()` + `sendParticipacao` atualizado.
- `src/components/steps/Step5Participacao.tsx` — nova UI.
- `src/components/steps/Step7Envio.tsx` — passar campos novos no `sendParticipacao` (alteração mínima, só os argumentos).

Sem novas dependências. Reúsa `CurrencyInput.tsx` para o modo Valor.

## Modelo de dados

`Participacao` (frontend `types/contract.ts` e backend `models/contract.py`):

```
tem_participacao: bool
valor_tipo?: "percentual" | "valor" | "outro"
valor_percentual?: string        // ex "10" (0–100)
valor_monetario?: number         // R$ (CurrencyInput devolve number)
valor_outro?: string             // texto livre
para_quem: string[]              // nomes de advogados (multi)
natureza?: string                // inalterado (Select existente)
responsavel_captacao?: string    // 1 nome
responsavel_gestao?: string      // 1 nome
contato_financeiro_nome?: string
contato_financeiro_email?: string
contato_financeiro_telefone?: string

// LEGADOS — mantidos opcionais para compat na edição de contratos salvos:
percentual_ou_valor?: string
contato_financeiro_cliente?: string
// (para_quem antigo era string; ver migração)
```

### Migração (backend `model_validator(mode="before")` em `Participacao`)
- Se `valor_tipo` ausente e `percentual_ou_valor` presente → `valor_tipo="outro"`, `valor_outro=percentual_ou_valor`.
- Se `para_quem` vier string (dado antigo) → converter para lista: `[]` se vazio, senão `[string]`.
- Manter coerção de `None`→"" existente para os campos string.
- `contato_financeiro_cliente` antigo: mantido; a ficha usa fallback (ver abaixo) quando os 3 campos novos estão vazios.

### Backend `Participacao` — tipos
- `para_quem: list[str] = []`
- demais novos: `Optional[...] = None`
- `valor_monetario: Optional[float] = None`

## Backend — endpoint de colaboradores

`GET /api/users/colaboradores` em `users.py`:
- Auth: `Depends(get_current_user)` (qualquer usuário logado).
- Retorna `{ "colaboradores": [{ "name": str, "email": str, "role": str }] }`, ordenado por `name`.
- Reusa `UserDB`. Sem dados sensíveis além de nome/email/role.

## Backend — ficha do financeiro (`email.py`)

`ParticipacaoEmailRequest` ganha os campos novos (todos opcionais, default "" / [] / None). As linhas da tabela passam a ser montadas assim (com fallback p/ legado):

- **Valor:** conforme `valor_tipo`:
  - `percentual` → linha `("Percentual", f"{valor_percentual}%")`
  - `valor` → linha `("Valor", formata_brl(valor_monetario))`
  - `outro` → linha `("Critério", valor_outro)`
  - se `valor_tipo` ausente → fallback `("Percentual/Valor", percentual_ou_valor)` (comportamento atual)
- **Para quem:** `("Para quem", ", ".join(para_quem))` (ou fallback string legado).
- **Resp. Captação / Resp. Gestão:** inalterado (strings).
- **Contato financeiro:** se algum dos 3 campos novos preenchido → linhas `("Contato — Nome", ...)`, `("Contato — E-mail", ...)`, `("Contato — Telefone", ...)` (só as não-vazias); senão fallback `("Contato Financeiro Cliente", contato_financeiro_cliente)`.

`formata_brl` = formatação simples R$ (reusar util existente se houver; senão `f"R$ {valor:,.2f}"` ajustado para pt-BR).

## Frontend — `Step5Participacao.tsx`

Carregar colaboradores no mount via `listColaboradores()` (estado `colaboradores`, `loadingColab`, `colabError`). Se falhar/vazio: mostrar aviso discreto; não bloquear (participação é opcional).

**Tipo de valor (radio):**
- 3 opções (Percentual / Valor / Outro). `valor_tipo` controla qual input aparece.
- Percentual: `Input type="number"` min 0 max 100 step 0.01, com sufixo "%" visual → grava `valor_percentual` (string).
- Valor: `CurrencyInput` → grava `valor_monetario` (number).
- Outro: `Input` texto → grava `valor_outro`.
- Ao trocar de tipo, os valores dos outros tipos são limpos (evita lixo).

**Para quem (multi):** lista de `Checkbox` (um por colaborador, label = nome). Marcar/desmarcar atualiza `para_quem: string[]` (nomes). Se lista vazia: aviso "Nenhum colaborador encontrado".

**Natureza:** Select inalterado.

**Responsáveis (captação, gestão):** `Select` (dropdown) com options = nomes dos colaboradores + placeholder. Grava string única.

**Contato financeiro (3 campos):**
- Nome: `Input` texto.
- E-mail: `Input type="email"` (validação de e-mail visual leve; não bloqueante).
- Telefone: `Input` com máscara BR `(00) 00000-0000` (só dígitos, formata ao digitar; 10–11 dígitos).

## Frontend — `api.ts`

- `listColaboradores(): Promise<{ name: string; email: string; role: string }[]>` → GET `/api/users/colaboradores`.
- `sendParticipacao(...)` — assinatura atualizada: adicionar `valor_tipo`, `valor_percentual`, `valor_monetario`, `valor_outro`, `para_quem` (array), `contato_financeiro_nome`, `contato_financeiro_email`, `contato_financeiro_telefone`. Manter campos legados opcionais para compat (podem ser omitidos).

## Frontend — `Step7Envio.tsx`

Atualizar as duas chamadas `sendParticipacao(...)` (em `handleSubmit` e `handleSaveOnly`) para enviar os campos estruturados de `data.participacao`. Alteração restrita aos argumentos — não toca na lógica de e-mail/recipients (minimiza sobreposição com PR #34).

## Tratamento de erros / casos de borda

- `listColaboradores` falha → Step5 mostra aviso e segue com listas vazias; usuário ainda pode preencher contato/valor. Participação continua opcional.
- Edição de contrato antigo → validator backend + normalização frontend convertem legado (string `percentual_ou_valor`, `para_quem` string, `contato_financeiro_cliente`) para os campos novos ao carregar. Frontend: ao montar Step5, se `valor_tipo` ausente mas `percentual_ou_valor` presente → `valor_tipo="outro"`, `valor_outro=percentual_ou_valor`; `para_quem` string → `[string]`; `contato_financeiro_cliente` → `contato_financeiro_nome` (best-effort).
- Telefone: aceita só dígitos, formata; valor salvo = string formatada.

## Critérios de sucesso

1. Etapa 5: radio Percentual/Valor/Outro mostra só o campo do tipo; Percentual aceita só número (0–100), Valor usa CurrencyInput, Outro é texto.
2. "Para quem" lista todos os colaboradores como checkboxes; seleção múltipla grava nomes.
3. Resp. captação e gestão são dropdowns de colaboradores (1 cada).
4. Contato em 3 campos (nome/e-mail/telefone com máscara).
5. Ficha enviada ao financeiro reflete os campos novos.
6. Contrato salvo antigo abre na edição sem quebrar (migração).
7. `GET /api/users/colaboradores` acessível a usuário não-admin.
8. `npm run build` e testes do backend passam.
