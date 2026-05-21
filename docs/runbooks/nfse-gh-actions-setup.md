# Setup GitHub Actions p/ nfse-sync

## Secrets necessários (repo Settings → Secrets → Actions)

- `HONORARIO_API_URL` — URL do backend Render (sem barra final), ex.: `https://honorario-cf-api.onrender.com`
- `NFSE_WORKER_TOKEN` — mesmo valor da env `NFSE_WORKER_TOKEN` no Render

## Variables (repo Settings → Variables → Actions)

- `PRESTADORES_CNPJS` — JSON array dos CNPJs, ex.: `["12345678000199"]`

## Verificação

- Manual: Actions → nfse-sync → Run workflow.
- Verificar logs do job (1 por CNPJ).
- Em falha, artifacts `screenshots-<cnpj>` ficam disponíveis 7 dias.
