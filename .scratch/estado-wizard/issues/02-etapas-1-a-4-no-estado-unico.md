# 02: Etapas 1 a 4 no Estado do wizard

**What to build:** auditar Contratante, Escopo, Honorários e Acessórios: tudo que é **Dado do contrato** e hoje fica em estado local (ex.: cláusulas adicionais em edição, endereço composto de CEP+número) passa a ser escrito no Estado do wizard; o que é **Dado de tela** (consulta de CNPJ/CEP, buscas) continua só na tela. O wizard deixa de ter normalizeFormData próprio.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Nenhum Dado do contrato só em estado local nas etapas 1 a 4
- [ ] Reabrir rascunho preserva os dados dessas etapas
- [ ] Dados de tela continuam fora do rascunho
