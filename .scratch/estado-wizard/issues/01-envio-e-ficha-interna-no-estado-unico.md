# 01: Envio (etapa 7) e Ficha interna no Estado do wizard

**What to build:** o módulo Estado do wizard nasce e passa a ser a única fonte do **Envio** (e-mails dos contratantes, testemunhas, sócio que assina) e da **Ficha interna**. A etapa 7 deixa de guardar cópia própria; reabrir rascunho/contrato traz tudo; o sócio sugerido vale no envio sem tocar no campo; esvaziar o campo de propósito o deixa vazio; abrir a etapa não marca o contrato como alterado. A leitura de formatos antigos da ficha interna mora no módulo.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Testes do módulo (abrir → alterar → ler) passam sem montar React
- [ ] Sócio: escolhido > sugerido > vazio; 'esvaziado' difere de 'não escolhido'
- [ ] Abrir a etapa 7 não altera o snapshot
- [ ] Etapa 7 sem useState dos dados do Envio nem efeito de cópia de volta
- [ ] Rascunhos e contratos antigos abrem iguais
