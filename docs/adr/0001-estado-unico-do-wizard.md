---
status: accepted
---

# Estado único do wizard, migrado etapa a etapa

O wizard guardava os **Dados do contrato** em três lugares (o estado do wizard, `useState` local de cada **Etapa** e cópias de volta por `useEffect`); campo novo esquecido em um deles sumia ao reabrir (#177, #179, #185, #169). Decidimos ter um módulo único de **Estado do wizard**, do qual as etapas só leem e no qual só escrevem, e migrar etapa a etapa começando pela **Etapa** 7 (Envio) e pela **Ficha interna**, onde nasceram os bugs; o sistema continua usável durante toda a migração.

- Só **Dados do contrato** vão ao **Rascunho**. **Dados de tela** (buscas digitadas, resultados de CNPJ/CEP, listas carregadas) ficam só na tela e se perdem ao fechar; texto digitado e ainda não confirmado não é salvo.
- Alternativa rejeitada: migrar tudo num PR só (mais limpo no fim, mas arrisca quebrar o que funciona e é difícil de revisar).
- Alternativa rejeitada: guardar também o texto não confirmado no rascunho (“não perco nada”), por poder salvar valor inválido ou incompleto.
