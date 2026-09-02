# Plano: Lista suspensa de advogados/sócios vinda do BANCO (Participação "Para quem" + correlatos)

> Pedido do usuário: o campo **Participação → "Para quem"** (e os demais campos que
> selecionam pessoa) deve oferecer uma **lista suspensa com todos os advogados e
> sócios**, e a fonte deve estar **no banco de dados** (não fixa no frontend).

## Estado ATUAL (verificado no código)

A lista suspensa **já é dinâmica e já vem do banco** — não está hardcoded:

- Endpoint `GET /api/users/colaboradores` (`backend/app/routers/users.py`, linha 62)
  lista a partir da tabela `users` (`UserDB`), ordenado por `name`, e devolve
  `{ colaboradores: [{name, email, role}] }`. Acesso: qualquer usuário autenticado.
- `frontend/src/components/steps/Step5Participacao.tsx` consome via `listColaboradores()`
  e usa em **3 campos**:
  - **"Para quem?"** → checkboxes (multi) — linha ~273
  - **"Responsável pela captação"** → `Select` — linha ~302
  - **"Responsável pela gestão do contrato"** → `Select` — linha ~310
- Persistência (`backend/app/models/contract.py` › `Participacao`):
  - `para_quem: list[str]` (nomes) · `responsavel_captacao`/`responsavel_gestao`: `str` (nome)
  - Há lógica legada (`optionsComSalvo`) que mantém um nome salvo mesmo fora da lista.

### Conclusão do diagnóstico
O problema **não é o frontend**. `UserDB` só contém pessoas que **já logaram via Azure
AD**, então o roster completo de advogados/sócios não aparece nos dropdowns. A solução
é **popular o banco** com o roster e fazer o endpoint enxergar esse roster (não só quem
logou).

## Decisão de Arquitetura (recomendada)

Criar uma **tabela de roster `ColaboradorDB`** (espelhando `TestemunhaDB`, já existente),
populá-la com os 21 nomes e **estender/repontar o endpoint de colaboradores** para
listar a partir dela, **mantendo a forma `{name, email, role}`** — assim o frontend não
precisa mudar.

Por que tabela dedicada e não semear `UserDB`:
- `UserDB` exige `azure_id` e `email` únicos (contas de login). Inserir 21 pessoas com
  `azure_id` fake polui a autenticação. Roster é cadastro, não login.
- Já existe o precedente `TestemunhaDB` (roster) — consistência (migração `0006`).

### Esquema proposto `ColaboradorDB`
`id` · `nome` (str, obrig.) · `email` (str, opcional) · `papel` (enum:
`socio|advogado|estagiario|recepcionista|financeiro|dev`) · `ativo` (bool, default true)
· `ordem` (int, default 0) · `created_at`/`updated_at`. Derivado:
`participavel = papel in {socio, advogado}`.

## Roster a popular (origem: usuário) — 21 pessoas

| Nome | Papel | Participável (advogado/sócio) |
|------|-------|:---:|
| André Fortes Chaves | advogado | sim |
| Caio César Amaral Franco | socio | sim |
| Clara Marques de Albuquerque | advogado | sim |
| Cristina Mascarenhas Diniz de Magalhães Santos | advogado | sim |
| Gabriel Siqueira Eliazar de Carvalho | socio | sim |
| Gabriela Peixoto Mello de Azevedo | advogado | sim |
| Marcello Silva Nunes Leite | advogado | sim |
| Marcelo Pinheiro Chagas | socio | sim |
| Marco Tulio Fonseca Furtado | socio | sim |
| Mariana Krollmann Fogli | socio | sim |
| Mônica Furtado Pinheiro Chagas | socio | sim |
| Natália Xavier Cunha | socio | sim |
| Sérgio Adolfo Eliazar de Carvalho | socio | sim |
| Ana Luíza Ricardo Oliveira | recepcionista | não |
| Isabela Vicentino Silva | estagiario | não |
| Lilian Silveira Correa | financeiro | não |
| Marcela Leite Kato | estagiario | não |
| Maria Karolyne Moraes Malard | recepcionista | não |
| Thaíza Alice Pereira da Silva | estagiario | não |
| Victor Barbosa Horta | estagiario | não |
| Paollo Sanchez | dev | não |

> **14 participáveis** (9 sócios + 5 advogados). "Para quem" e responsáveis listam só os
> participáveis. Emails não foram fornecidos — semear vazio e completar depois (admin).
> Por isso `email` é opcional.

## Grafo de Dependências

```
T1 ColaboradorDB + migração 0007 (schema)
      └── T2 Seed idempotente dos 21
              └── T3 Endpoint lista do roster (?participavel=true), forma {name,email,role}
                      └── T4 Frontend: filtrar participáveis nos 3 campos (ajuste mínimo)
                              └── T5 (opcional) Tela admin de colaboradores (CRUD)
```

## Tarefas

### Fase 1 — Banco

#### T1: Modelo `ColaboradorDB` + migração `0007_colaboradores`
**Descrição:** Adicionar `ColaboradorDB` em `app/database.py` (espelhar `TestemunhaDB`)
e migração alembic `0007_colaboradores` (down_revision `0006_testemunhas`), no estilo
das versões existentes.
**Aceite:**
- [ ] Tabela criada via `alembic upgrade head`; `downgrade -1` ok
- [ ] Campos: `id, nome, email?, papel, ativo, ordem, created_at, updated_at`
**Verificação:** `cd backend && alembic upgrade head && alembic downgrade -1`; `pytest -q` verde
**Dependências:** Nenhuma. **Arquivos:** `backend/app/database.py`,
`backend/alembic/versions/0007_colaboradores.py`. **Escopo:** S

#### T2: Seed idempotente dos 21 colaboradores
**Descrição:** Popular o roster com papéis corretos. Idempotente por `nome` (upsert),
no padrão de `backend/seed_test_users.py` **ou** seed de dados na própria migração `0007`.
**Aceite:**
- [ ] 21 registros; 14 com `participavel=true` (9 sócios, 5 advogados)
- [ ] Rodar 2x não duplica
**Verificação:** executar o seed; teste conta 21 total / 14 participáveis
**Dependências:** T1. **Arquivos:** `backend/seed_colaboradores.py` (ou dados em `0007`).
**Escopo:** S

### ✅ Checkpoint A (T1–T2)
- [ ] `alembic upgrade head` limpo, tabela populada, testes verdes — revisar com humano

### Fase 2 — API

#### T3: Endpoint de colaboradores lê o roster
**Descrição:** Fazer a listagem vir de `ColaboradorDB`. Preferência: **estender
`GET /api/users/colaboradores`** (ou criar `GET /api/colaboradores`) com filtro
`?participavel=true`, mantendo a forma `{name, email, role}` (map `nome→name`,
`papel→role`) para **compatibilidade com o frontend atual**. `ativo=true` por padrão,
ordenar por `ordem`,`nome`.
**Aceite:**
- [ ] `GET .../colaboradores?participavel=true` retorna os 14 advogados/sócios
- [ ] Sem filtro retorna os 21
- [ ] Forma de resposta inalterada (frontend continua funcionando)
**Verificação:** `pytest backend/tests/test_colaboradores.py -q` (ajustar/expandir);
chamada manual confere JSON
**Dependências:** T1, T2. **Arquivos:** `backend/app/routers/users.py` (ou novo
`routers/colaboradores.py` + registro em `main.py`), `backend/tests/test_colaboradores.py`.
**Escopo:** M

### ✅ Checkpoint B (T3)
- [ ] DB → endpoint testado ponta-a-ponta; frontend lista os 14 sem alteração

### Fase 3 — Frontend (ajuste mínimo)

#### T4: Filtrar participáveis nos campos de pessoa do Step5
**Descrição:** `listColaboradores()` em `frontend/src/app/lib/api.ts` aceitar filtro
(`participavel`) e os 3 campos ("Para quem", "Resp. captação", "Resp. gestão") usarem a
lista de advogados/sócios. (Já é dropdown; muda só a fonte/filtro.)
**Aceite:**
- [ ] Os 3 campos mostram os 14 advogados/sócios vindos do banco
- [ ] Nada hardcoded no front; seleção persiste e gera contrato igual
**Verificação:** `cd frontend && npm run build`; conferência manual do wizard
**Dependências:** T3. **Arquivos:** `frontend/src/app/lib/api.ts`,
`frontend/src/components/steps/Step5Participacao.tsx`. **Escopo:** S

### Fase 4 — Tela admin (OBRIGATÓRIA)

#### T5: Tela admin de colaboradores (CRUD)
**Descrição:** Router `routers/colaboradores.py` (ou estender users) com
`GET/POST/PATCH/DELETE` (soft delete via `ativo=false`), restrito a admin
(`require_admin`), + página em `frontend/src/app/admin/` nos moldes da gestão de
testemunhas. Permite adicionar/editar/desativar e completar emails/papel.
**Aceite:**
- [ ] CRUD funcional; admin altera nome/email/papel/ativo/ordem
- [ ] Soft delete não remove fisicamente
- [ ] Lista do wizard reflete alterações
**Verificação:** `pytest backend/tests/test_colaboradores.py -q`; `cd frontend && npm run build`; manual
**Dependências:** T1–T3. **Arquivos:** `backend/app/routers/colaboradores.py`,
`backend/app/main.py`, `frontend/src/app/admin/colaboradores/page.tsx`,
`frontend/src/app/lib/api.ts`. **Escopo:** M

### ✅ Checkpoint Final
- [ ] DB → API → dropdown → contrato; `pytest` backend + `npm run build` verdes

## Riscos e Mitigações

| Risco | Impacto | Mitigação |
|------|---------|-----------|
| Mudar a fonte de `/colaboradores` quebrar quem depende de UserDB | Médio | Manter forma `{name,email,role}`; decidir em T3 se mescla UserDB+roster ou substitui |
| Emails ausentes no roster | Baixo | `email` opcional; completar via T5/admin |
| Acentuação dos nomes no seed | Baixo | Seed UTF-8; idempotência por `nome` |
| Persistência por nome (não id) | Baixo | Mantida; nomes do roster são estáveis. Migração para id = evolução futura |

## Decisões do usuário (FECHADAS)
1. Campos de pessoa listam **só advogados/sócios (14)**. → `?participavel=true` por padrão nesses campos.
2. Endpoint **lê só o roster novo** (`ColaboradorDB`). `UserDB` fica exclusivo para login.
3. **Tela admin (CRUD) agora** → **T5 promovida a obrigatória**.
4. Usuário **tem os emails** → semear nome+papel+email. **PENDENTE: colar a lista de emails.**

## ⚠️ Bloqueio único antes do seed (T2)
Faltam os **emails** dos 21 colaboradores. Implementação de T1/T3/T5 não depende disso;
só o conteúdo do seed (T2). Colar no formato: `Nome — email`.

---
> Salvo em arquivo próprio para **não sobrescrever** `tasks/plan.md` (plano de
> Testemunhas). Diagnóstico feito lendo `users.py`/`participacoes.py`/`Step5`/`contract.py`.
