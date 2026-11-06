# 05: Rascunho como módulo e retomada na etapa exata

**What to build:** abrir, salvar e encerrar o **Rascunho** passam por um módulo com adapters (servidor, cópia local, memória nos testes). Retomar reabre na etapa exata, até a 7. As regras de apagar (gerar, salvar versão, descartar) ficam num só lugar.

**Blocked by:** 01

**Status:** done

**Entregue:** `rascunho.ts` (retomar/apagar com `Armazem`, testado com adapter em memória), `rascunhoArmazem.ts` (adapter real), retomada na etapa exata até a 7, e as regras de apagar (descartar, gerar, rascunho antigo, PUT em voo) numa função só. Pendente no 06: marcar Revisão/Prévia desatualizadas ao reabrir na 6/7.

- [ ] Reabrir volta na etapa em que parou, inclusive a 7
- [ ] Testes com adapter em memória (sem API)
- [ ] Regras de apagar o rascunho num só lugar
