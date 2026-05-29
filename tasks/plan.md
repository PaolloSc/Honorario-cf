# Plano de Implementação: Testemunhas Digitais (roster) + Ficha pós-assinatura

## Overview
Escritório de advocacia → testemunhas são pessoas recorrentes. Fluxo:

1. **Cadastro de testemunhas (roster)** — tabela no banco com testemunhas frequentes (nome+email, ativa). CRUD próprio.
2. **No envio p/ assinatura** o advogado seleciona N testemunhas do roster (multi) e/ou adiciona avulsas. **Testemunha 1 = Lilian Siqueira (financeiro)** sempre injetada automaticamente. Sem teto de quantidade.
3. **Testemunhas assinam digitalmente** no DocuSeal (papéis `Testemunha 1..N`).
4. **Financeiro não recebe email na geração nem no envio.** A **ficha de participação** vai ao financeiro **só no webhook `submission.completed`** (todos assinaram). Lilian recebe o contrato assinado via DocuSeal.

### Quem recebe o quê, quando
| Momento | Financeiro |
|---|---|
| Geração | nada |
| Envio p/ assinatura | nada por email; Lilian + testemunhas selecionadas entram no DocuSeal |
| Todos assinaram (`submission.completed`) | **ficha de participação** (email) + contrato assinado via DocuSeal |

## Decisões de Arquitetura
- **Roster dedicado** `TestemunhaDB` (nome, email, ativo, created_by, timestamps). Escolhido em vez de reusar `UserDB`/colaboradores. CRUD em `routers/testemunhas.py`. Migration alembic `0006`.
- **Lilian fixa** via settings `testemunha1_nome`/`testemunha1_email` (email único; `financeiro_email` é lista, não serve p/ submitter). Injetada no backend como `role: "Testemunha"`, garantida como `Testemunha 1`.
- **Testemunhas = signatárias DocuSeal**, papel `Testemunha` numerado pela dedup já existente. `_ROLE_ORDER` += `Testemunha: 4` (assinam por último). Sem limite rígido de quantidade.
- **Gerador DOCX** (`_add_signatures`) renderiza campos digitais p/ papéis `Testemunha*`; bloco físico em branco só no fallback (geração inicial sem signatários).
- **Frontend:** página simples de gestão do roster + seleção (multiselect do roster + add avulsa) na tela de envio. Aviso "Testemunha 1 (financeiro) incluída automaticamente".
- **Ficha de participação** reaproveita lógica atual de `_send_participacao_to_financeiro`, disparada no `submission.completed`, idempotente via audit `envio_participacao_final`. Destinatário = `financeiro_email` (lista).
- **Remoções no `send_for_signature`:** tirar `_send_contract_to_financeiro` e `_send_participacao_to_financeiro`.
- Envio ao financeiro nunca quebra fluxo (try/except + log).

## Grafo de Dependências
```
Task 1 (TestemunhaDB + migration)
   └── Task 2 (CRUD roster) ─────────────┐
Task 3 (settings Lilian)                  │
   └── Task 4 (injeta Lilian + papéis Testemunha + ordem) ── Task 5 (DOCX digital)
                                          │
   Task 6 (frontend: gestão roster + seleção no envio) ← Task 2,4
Task 7 (ficha só no webhook; remove envios send-for-signature) ── independe
Task 8 (testes) ← 2,4,5,7
```

## Lista de Tarefas

### Fase 1: Roster (backend)

#### Task 1: Modelo `TestemunhaDB` + migration 0006
**Descrição:** Criar `TestemunhaDB` em `app/database.py` (id, nome, email, ativo=True, created_by, created_at, updated_at) e migration alembic `0006_testemunhas` espelhando o estilo das versões 0001–0005.
**Acceptance criteria:**
- [ ] Tabela criada via `alembic upgrade head`.
- [ ] Modelo importável e com defaults corretos.
**Verification:**
- [ ] `alembic upgrade head` + `alembic downgrade -1` sem erro.
- [ ] `pytest -q` (conftest cria schema) verde.
**Dependencies:** None
**Files likely touched:** `backend/app/database.py`, `backend/alembic/versions/0006_testemunhas.py`
**Estimated scope:** S

#### Task 2: CRUD do roster (`routers/testemunhas.py`)
**Descrição:** Endpoints: `GET /api/testemunhas` (ativas), `POST` (criar), `PATCH /{id}` (editar/ativar-desativar), `DELETE /{id}` (soft delete via `ativo=False`). Autenticado. Registrar router no `main.py`.
**Acceptance criteria:**
- [ ] CRUD funcional; listagem retorna só ativas por padrão.
- [ ] Validação de email.
**Verification:**
- [ ] Teste novo `tests/test_testemunhas.py` cobre list/create/patch/delete.
- [ ] `pytest tests/test_testemunhas.py -q`.
**Dependencies:** Task 1
**Files likely touched:** `backend/app/routers/testemunhas.py`, `backend/app/main.py`, `backend/tests/test_testemunhas.py`
**Estimated scope:** M

### Checkpoint: Roster
- [ ] CRUD verde, migration ok. Revisar c/ humano.

### Fase 2: Testemunhas no envio (backend)

#### Task 3: Settings da testemunha fixa
**Descrição:** `testemunha1_nome` ("Lilian Siqueira") + `testemunha1_email` (env `TESTEMUNHA1_EMAIL`, default financeiro@...) em `config.py`; doc no `.env.example`.
**Acceptance criteria:** [ ] settings existem e leem env.
**Verification:** [ ] import imprime valores.
**Dependencies:** None
**Files likely touched:** `backend/app/config.py`, `backend/.env.example`
**Estimated scope:** XS

#### Task 4: Injetar Lilian + papéis Testemunha + ordem no `send_for_signature`
**Descrição:** Injetar Lilian (`role: "Testemunha"`) se ausente, garantindo `Testemunha 1`. Aceitar testemunhas do payload (`role: "Testemunha"`). Manter dedup → `Testemunha 1..N`. `_ROLE_ORDER` += `Testemunha: 4`.
**Acceptance criteria:**
- [ ] Submissão sempre tem Lilian = `Testemunha 1` (email `testemunha1_email`).
- [ ] Testemunhas do payload viram `Testemunha 2..N`, `order=4`.
- [ ] Papéis únicos.
**Verification:**
- [ ] Teste captura `signatarios`: Lilian presente, ordem 4, numeração correta.
- [ ] `pytest tests/test_send_for_signature.py -q`.
**Dependencies:** Task 3
**Files likely touched:** `backend/app/routers/docuseal.py`, `backend/tests/test_send_for_signature.py`
**Estimated scope:** M

#### Task 5: Campos digitais de testemunha no gerador DOCX
**Descrição:** `_add_signatures`: quando `signatario_roles` contém `Testemunha*`, renderizar `{{Assinatura <nome>|signature|<role>}}` + "TESTEMUNHA N: NOME"; bloco físico só no fallback.
**Acceptance criteria:**
- [ ] DOCX regenerado no envio tem campo digital p/ cada testemunha.
- [ ] Geração inicial sem signatários mantém bloco físico.
**Verification:**
- [ ] Teste: gerar c/ `Testemunha 1` em `signatario_roles` → DOCX contém `|signature|Testemunha 1`.
- [ ] `pytest tests/test_contract_generator*.py -q`.
**Dependencies:** Task 4
**Files likely touched:** `backend/app/services/contract_generator.py`, `backend/tests/`
**Estimated scope:** M

### Checkpoint: Backend testemunhas
- [ ] Envio cria submissão c/ Lilian + selecionadas; DOCX digital. Suite verde. Revisar.

### Fase 3: Frontend

#### Task 6: Gestão do roster + seleção no envio
**Descrição:** (a) Página/seção simples p/ gerenciar roster (listar/criar/editar/desativar). (b) Na tela de envio (`Step7Envio.tsx` e `contracts/[id]/page.tsx`): multiselect das testemunhas ativas do roster + opção "adicionar avulsa" (nome+email). Enviar como `signatarios` `role:"Testemunha"`. Aviso sobre Lilian automática. Tipos/API em `lib/api.ts`.
**Acceptance criteria:**
- [ ] Advogado gerencia roster e seleciona N testemunhas no envio (+ avulsas).
- [ ] Payload inclui testemunhas como `role:"Testemunha"`.
**Verification:**
- [ ] `cd frontend && npm run build` ok.
- [ ] Manual: enviar c/ 2 do roster + 1 avulsa → submissão com Testemunha 1 (Lilian) + 2/3/4.
**Dependencies:** Task 2, Task 4
**Files likely touched:** `frontend/src/app/lib/api.ts`, `frontend/src/components/steps/Step7Envio.tsx`, `frontend/src/app/contracts/[id]/page.tsx`, nova página de roster
**Estimated scope:** L

### Fase 4: Ficha pós-assinatura

#### Task 7: Ficha só no webhook completed; remover envios do send-for-signature
**Descrição:** Remover `_send_contract_to_financeiro`/`_send_participacao_to_financeiro` do `send_for_signature`. Webhook `submission.completed` → ficha ao `financeiro_email` (se `tem_participacao`), idempotente via audit `envio_participacao_final`, sem `CurrentUser` (usar `contract.created_by`/`"sistema"`). `declined` não envia.
**Acceptance criteria:**
- [ ] send-for-signature: 0 email ao financeiro.
- [ ] completed: ficha 1x; reentrega não reenvia.
- [ ] declined: nada.
**Verification:**
- [ ] Testes webhook completed (1x + idempotência) e send silencioso.
- [ ] `pytest tests/test_send_for_signature.py -q`.
**Dependencies:** None (coordena c/ Task 4 no mesmo arquivo)
**Files likely touched:** `backend/app/routers/docuseal.py`, `backend/tests/`
**Estimated scope:** M

### Checkpoint: Fluxo financeiro
- [ ] Geração=0, envio=0, completed=ficha 1x. Revisar.

### Fase 5: Testes

#### Task 8: Cobertura ponta a ponta
**Descrição:** Roster CRUD, injeção Lilian, ordem/papéis/numeração testemunha, DOCX digital, webhook completed (ficha+idempotência), declined, send silencioso.
**Acceptance criteria:** [ ] pontos cobertos; sem testes obsoletos.
**Verification:** [ ] `cd backend && pytest -q` verde.
**Dependencies:** Task 2,4,5,7
**Files likely touched:** `backend/tests/*`
**Estimated scope:** M

### Checkpoint: Completo
- [ ] Back+front verdes, pronto p/ revisão.

## Riscos e Mitigações
| Risco | Impacto | Mitigação |
|---|---|---|
| Template DocuSeal: papel ↔ campo de assinatura tem que bater | Alto | Task 5 gera `|signature|Testemunha N` p/ cada papel |
| Muitas testemunhas → muitos campos/submitters no template | Médio | DOCX gerado dinamicamente por papel; validar limite prático do DocuSeal |
| `financeiro_email` é lista; submitter exige 1 email | Médio | Setting `testemunha1_email` dedicada |
| Webhook reentregue duplica ficha | Médio | Idempotência via audit `envio_participacao_final` |
| FS efêmero (Render) | Médio | `_resolve_contract_filepath` regenera do `form_data_json` |
| Assinatura sequencial trava se testemunha não assina | Médio | Confirmar sequencial vs paralelo no DocuSeal; testemunha = último |

## Questões em Aberto
- Roster precisa ser **restrito a admin** ou qualquer advogado gerencia? (assumido: qualquer autenticado)
- Email extra do contrato assinado ao financeiro no completed além da ficha? (assumido NÃO)
- Gestão do roster: página dedicada nova ou seção dentro de tela existente? (assumido: página/seção simples nova)
