# 07: Remover cópias antigas e fechar a migração

**What to build:** apagar normalizeFormData e os estados/efeitos de cópia que sobraram; ContractWizard só compõe. Atualizar GLOSSARY/ADR se algo mudou.

**Blocked by:** 02, 05

**Status:** done

**Auditoria:** `normalizeFormData`/`INITIAL_DATA` já saíram do wizard (tickets 01/02); sem outras cópias; o estado local restante é Dado de tela. Entregue: `normalizarFormData` preserva campos desconhecidos (topo, acessórios, ficha) — antes uma lista explícita descartava, p.ex., `contato_financeiro_cliente` ao reabrir —, só as chaves do formato antigo saem. A conversão ao abrir foi mantida (as 3 versões puladas pelo script dependem dela).

- [ ] Nenhuma etapa guarda Dado do contrato fora do Estado do wizard
- [ ] Campo novo no contrato = um lugar
