# Spec: Estado único do wizard

Vocabulário em `GLOSSARY.md`; decisões em `docs/adr/0001` e `0002`.

## Problem Statement

O advogado perde ou vê trocados dados do contrato ao reabrir um rascunho ou um contrato para edição (ajustes de texto, e-mails de envio, testemunhas, sócio que assina, base da participação). A causa é que os **Dados do contrato** vivem em vários lugares, e cada campo novo precisa ser lembrado em 3 a 5 arquivos. Em produção, o botão de assinatura já ficou sem efeito por causa do sócio guardado só na tela.

## Solution

Um **Estado do wizard** único: todas as **Etapas** leem dele e escrevem nele; o que é **Dado de tela** fica só na tela. O **Rascunho** guarda exatamente os **Dados do contrato** e reabre na etapa em que o advogado parou, até a 7, marcando a **Revisão por IA** e a **Prévia** como **Revisão desatualizada** se os dados mudaram.

## User Stories

1. Como advogado, quero reabrir um rascunho e ver tudo como deixei (inclusive e-mails, testemunhas e sócio da etapa 7), para não refazer o que já fiz.
2. Como advogado, quero que o sócio sugerido pelo sistema fique valendo no envio sem eu ter de tocar no campo, para enviar com um clique.
3. Como advogado, quero que o campo do sócio, se eu o esvaziar de propósito, fique vazio e peça a escolha, para não assinar com a pessoa errada.
4. Como advogado, quero que abrir a etapa 7 não marque o contrato como alterado, para não receber o aviso de "alterações não salvas" sem ter mexido em nada.
5. Como advogado, quero reabrir o rascunho exatamente na etapa em que parei, para continuar sem navegar de novo.
6. Como advogado, quero ser avisado de que a revisão por IA e a prévia estão desatualizadas quando mudei dados depois delas, para não gerar com texto velho.
7. Como advogado, quero que contratos e rascunhos antigos continuem abrindo sem perda, para não perder trabalho já feito.
8. Como financeiro, quero que a ficha interna (contato financeiro, responsável pela gestão, participação) chegue completa ao sistema, mesmo sem participação, para lançar o cliente.
9. Como pessoa que mantém o sistema, quero adicionar um campo ao contrato em um só lugar, para não esquecê-lo ao reabrir.
10. Como pessoa que mantém o sistema, quero testar a leitura, a alteração e a migração do formato sem montar a tela, para pegar o bug antes da produção.
11. Como responsável pelo banco, quero converter os dados antigos com backup, dry-run e meu ok final, para não correr risco em produção.

## Implementation Decisions

- Módulo **Estado do wizard** profundo: interface pequena para abrir dados (qualquer formato conhecido), alterar uma parte, ler o **Envio** e a **Ficha interna** já resolvidos (com padrões e sugestões), e obter o snapshot a gravar. A migração de formatos antigos vive dentro dele.
- O **Envio** é derivado dos dados: e-mails dos contratantes, testemunhas e sócio que assina. Escolhas explícitas valem sobre sugestões; "não escolhido" é diferente de "esvaziado de propósito".
- Só gravar no **Estado do wizard** por ação da pessoa; ler ou sugerir nunca altera os dados.
- **Dados de tela** nunca entram no **Rascunho** (ADR 0001).
- Migração etapa a etapa: primeiro Envio e Ficha interna; depois Etapas 1 a 4; depois o ciclo de vida do **Rascunho**.
- Formato versionado a partir do ticket 03; conversão do banco só no ticket 04, com backup, dry-run e ok final (ADR 0002).
- **Retomar** reabre na etapa exata (até a 7); **Revisão desatualizada** detectada comparando os dados atuais com os da última revisão (ADR 0002).

## Testing Decisions

- Bom teste: só comportamento externo do módulo (abrir → alterar → ler/snapshot), sem montar React.
- Um seam só: a interface do módulo **Estado do wizard**. Os testes cruzam o mesmo seam que as etapas.
- Prior art: os `*.check.ts` de `frontend/src/app/lib` (ex.: `rascunhoLocal.check.ts`, `trocaEscopo.check.ts`), rodados com `node --experimental-strip-types`.
- O ciclo de vida do **Rascunho** (ticket 05) usa um adapter em memória no lugar do servidor e da cópia local.

## Out of Scope

- Reescrever as etapas ou o visual; o gerador de contrato; o fluxo de assinatura; geração de tipos TS a partir do Pydantic (candidato separado do relatório).
- Contratos de consumidor aéreo e substabelecimento (outros formatos).

## Further Notes

- Em produção (05/11/2026): 4 rascunhos e 28 contratos; 3 com vigência no formato antigo, 2 com parcelamento antigo, nenhum com participação no formato antigo.
