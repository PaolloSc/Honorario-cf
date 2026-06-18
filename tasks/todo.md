# TODO: Testemunhas Digitais (roster) + Ficha pós-assinatura

## Fase 1 — Roster (backend)
- [ ] **Task 1** — `TestemunhaDB` (nome,email,ativo,created_by,timestamps) + migration alembic `0006_testemunhas`
- [ ] **Task 2** — CRUD `routers/testemunhas.py` (GET ativas / POST / PATCH / DELETE soft) + registrar no `main.py` + `test_testemunhas.py`
- [ ] **Checkpoint Roster** — CRUD verde, migration up/down ok → revisar

## Fase 2 — Testemunhas no envio (backend)
- [ ] **Task 3** — settings `testemunha1_nome`/`testemunha1_email` + `.env.example`
- [ ] **Task 4** — `send_for_signature`: injeta Lilian `Testemunha`, aceita payload, dedup `Testemunha 1..N`, `_ROLE_ORDER` += `Testemunha:4`
- [ ] **Task 5** — `_add_signatures`: campos digitais `|signature|Testemunha N`; físico só fallback
- [ ] **Checkpoint Backend** — submissão c/ Lilian + selecionadas, DOCX digital, suite verde → revisar

## Fase 3 — Frontend
- [ ] **Task 6** — gestão roster (list/create/edit/desativar) + multiselect no envio + add avulsa; payload `role:"Testemunha"`; aviso Lilian automática
  - [ ] `npm run build` ok

## Fase 4 — Ficha pós-assinatura
- [ ] **Task 7** — remove envios do send-for-signature; webhook `completed` → ficha (se `tem_participacao`) idempotente via audit `envio_participacao_final`; `declined` nada
- [ ] **Checkpoint Financeiro** — geração=0, envio=0, completed=ficha 1x → revisar

## Fase 5 — Testes
- [ ] **Task 8** — roster, injeção Lilian, ordem/numeração, DOCX digital, completed+idempotência, declined, send silencioso
  - [ ] `cd backend && pytest -q` verde
- [ ] **Checkpoint Completo** — back+front verdes, pronto p/ revisão

## Questões em aberto (confirmar)
- Roster restrito a admin? (assumido: qualquer autenticado)
- Email extra do contrato assinado ao financeiro no completed? (assumido NÃO)
- Gestão roster: página nova dedicada? (assumido: sim, simples)
