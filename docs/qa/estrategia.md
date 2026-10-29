# Estratégia de testes

## Pirâmide
- **Base (já existe): pytest** (~830 testes) e as verificações `*.check.ts`. Cobrem regra de negócio, texto do contrato e validação. Continua sendo o lugar certo para texto jurídico e cálculo.
- **Topo (novo): E2E com Playwright, poucos e sobre fluxo crítico.** Vê o que o pytest não vê: máscara de campo, passos do wizard, botão desabilitado, iframe de prévia, login.
- Sem camada do meio nova: a API já é testada pelo pytest via `TestClient`.

## O que vai para o E2E (e o que não)
Entra: fluxo de ponta a ponta que o advogado percebe quando quebra — convite/login, wizard até a prévia, distrato (pagamento, contencioso), substabelecimento com CNJ.
Não entra: variações de texto (pytest), layout fino (revisão visual), integrações externas (DocuSeal, Graph, Legal One, DeepSeek).

## Ferramentas
Playwright Test (`e2e/`), Chrome instalado no sistema (`channel: "chrome"`, nada para baixar). Um worker, sem paralelismo: homolog usa um banco só.

## Regras de segurança dos testes
1. Só homolog ou localhost; `fixtures.ts` aborta em qualquer outro host.
2. Todo dado criado leva `[TESTE-QA-DELETAR]` no nome; a limpeza apaga só o que tem a marca.
3. Nunca clicar em "Gerar e Enviar", "Enviar para Assinatura" nem "Revisar com IA". "Apenas Gerar Contrato" também fica de fora: tenta mandar a ficha ao financeiro por e-mail.
4. Token e senhas só por variável de ambiente.

## Critérios
- **Entrada:** `tsc` e pytest verdes; o alvo no mesmo commit do que se quer testar.
- **Saída (por PR):** E2E verde no homolog atualizado. Falha por homolog desatualizado não é regressão: vira nota no relatório.
- **Próximo passo (CI):** job manual (`workflow_dispatch`) rodando `e2e/` contra homolog antes de promover para produção.

## Evidência
`npx playwright test` grava `e2e/report/` (HTML, JSON, print e trace de cada falha). O relatório cita o que passou, o que falhou com print e o que não rodou, com o motivo.
