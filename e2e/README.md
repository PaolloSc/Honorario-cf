# E2E (Playwright) — Honorário C&F

Testes de ponta a ponta no navegador. Estratégia em `docs/qa/estrategia.md`, plano em `docs/qa/plano.md`.

## Rodar
```bash
cd e2e && npm install
export E2E_FRONT=https://<frontend-homolog>   # URL do homolog (fora do repositório público)
export E2E_BACK=https://<backend-homolog>
export E2E_TOKEN=...                          # token do convite; nunca no repositório
npx playwright test
# local: E2E_FRONT=http://localhost:3000 E2E_BACK=http://localhost:8000 E2E_TOKEN=<CONVITE_TOKEN do .env>
```
Precisa do Google Chrome instalado. O relatório fica em `e2e/report/` (ignorado pelo git).

## Antes de rodar
- O alvo tem de estar no commit que você quer testar (homolog costuma ficar atrás do `master`).
- O colaborador `Ana Teste Socia` (papel sócio, OAB MG 111.111) precisa existir: é quem os testes escolhem como substabelecente e responsável. Em homolog já existe; local, crie em Administração.

## Dados e limpeza
Tudo que os testes criam leva `[TESTE-QA-DELETAR]` no nome (contratos de origem, rascunhos do wizard). Não há endpoint para apagar contratos: a limpeza é por SQL no banco do ambiente, só nas linhas com a marca. Nada é enviado para assinatura nem por e-mail.
