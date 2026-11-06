# 02: Etapas 1 a 4 no Estado do wizard

**What to build:** auditar Contratante, Escopo, Honorários e Acessórios: tudo que é **Dado do contrato** e hoje fica em estado local (ex.: cláusulas adicionais em edição, endereço composto de CEP+número) passa a ser escrito no Estado do wizard; o que é **Dado de tela** (consulta de CNPJ/CEP, buscas) continua só na tela. O wizard deixa de ter normalizeFormData próprio.

**Blocked by:** 01

**Status:** done

**Auditoria (resultado):** nas etapas 1 a 4 todo Dado do contrato já é escrito pelas props; o estado local restante é Dado de tela: consulta de CNPJ/CEP, busca de cliente, aviso de origem, `pendentes`/`previa` do Step3, `guardado` (desfazer) do Step2, lista de cláusulas com linhas vazias do Step4 (só o texto vai ao contrato) e CEP/número/complemento do Step1, remontados do endereço salvo. Entregue: `endereco.ts` (montar/desmontar, com teste de ida e volta) e teste de ida e volta dos dados das etapas 1 a 4 pelo Estado do wizard.

- [ ] Nenhum Dado do contrato só em estado local nas etapas 1 a 4
- [ ] Reabrir rascunho preserva os dados dessas etapas
- [ ] Dados de tela continuam fora do rascunho
