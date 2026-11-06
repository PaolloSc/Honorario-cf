# 06: Revisão por IA e Prévia desatualizadas

**What to build:** quando os Dados do contrato mudam depois da última **Revisão por IA** ou **Prévia**, a etapa 7 mostra **Revisão desatualizada** e refaz a revisão antes de permitir gerar/enviar.

**Blocked by:** 05

**Status:** done

**Entregue:** `revisao.ts` (chave dos dados sem o Envio; nenhuma/em_dia/desatualizada) com teste; a etapa 7 reaproveita a revisão em dia (sem IA), avisa e refaz a desatualizada, avisa ao retomar na 6/7 e bloqueia gerar/enviar enquanto revisa. A revisão fica no wizard (sessão), não no rascunho (ADR 0001).

- [ ] Dado alterado depois da revisão → aviso e revisão refeita
- [ ] Sem alteração, nada é refeito (não gasta IA)
- [ ] Retomar o rascunho na etapa 7 já avisa se estiver desatualizada
