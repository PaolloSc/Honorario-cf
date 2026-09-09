# TODO: Lista suspensa de advogados/sócios via banco (Participação "Para quem")

> Diagnóstico: o dropdown JÁ vem do banco (`/api/users/colaboradores` ← `UserDB`),
> mas `UserDB` só tem quem logou. Falta popular o roster no banco.
> Plano: `tasks/plan-colaboradores-dropdown.md`

## Fase 1 — Banco
- [ ] **T1** `ColaboradorDB` (nome, email?, papel[socio/advogado/estagiario/recepcionista/financeiro/dev], ativo, ordem) + migração `0007_colaboradores`
- [ ] **T2** Seed idempotente dos 21 (14 participáveis: 9 sócios + 5 advogados)
- [ ] ✅ **Checkpoint A**: `alembic upgrade head` limpo + tabela populada + testes verdes

## Fase 2 — API
- [ ] **T3** Endpoint de colaboradores lê o roster com `?participavel=true`, mantendo forma `{name,email,role}` (compat. frontend)
- [ ] ✅ **Checkpoint B**: DB → endpoint testado; front lista os 14 sem alteração

## Fase 3 — Frontend (mínimo)
- [ ] **T4** `listColaboradores()` aceita filtro `participavel`; 3 campos do Step5 (Para quem / Resp. captação / Resp. gestão) usam advogados/sócios

## Fase 4 — Tela admin (OBRIGATÓRIA)
- [ ] **T5** CRUD de colaboradores (router admin + página `admin/colaboradores`): add/editar/desativar/email/papel
- [ ] ✅ **Checkpoint Final**: DB → API → dropdown → contrato; `pytest` + `npm run build` verdes

## Decisões (fechadas)
- ✅ Campos listam só os 14 participáveis (`?participavel=true`)
- ✅ Endpoint lê só o roster novo (UserDB só p/ login)
- ✅ Tela admin agora (T5 obrigatória)
- ✅ Usuário tem emails → semear com email

## Status implementação — TODOS T1–T5 ENTREGUES ✅
- ✅ T1: `ColaboradorDB` + migração `0007` — up/down verificado (9 colunas, drop limpo)
- ✅ T2: `seed_colaboradores.py` — 21 criados, idempotente (rerun = 0 criados/21 atualizados), 13 participáveis
- ✅ T3: `/api/users/colaboradores?participavel=&include_inactive=` lê roster (forma `{name,email,role}`)
- ✅ T4: `listColaboradores({participavel:true})` + Step5 (Para quem/Resp. captação/Resp. gestão) filtram advogados/sócios
- ✅ T5: router `/api/colaboradores` (admin CRUD) + página `admin/colaboradores`
- ✅ Backend: 160 testes verdes · Frontend: build OK

## Pendências de dados (não-bloqueantes)
- [ ] Emails faltantes (semeados vazios): **Mônica Furtado** (sócia), **Ana Luíza**, **Maria Karolyne** (recepção) — completar via tela admin
- [ ] Confirmar se **Daniel Araújo** (`suporte@`) e **`marketing@`** entram no roster (não semeados)
