# Produção via Docker — backend + DocuSeal (API key, webhook, Vercel)

Arquitetura de produção:

- **Frontend** → Vercel (projeto `honorario-cf`, root directory `frontend/`)
- **Backend (FastAPI) + DocuSeal** → uma VM com Docker, usando os arquivos
  de `deploy/` (Caddy na frente com HTTPS automático para os dois domínios)

> **Importante:** o backend NÃO roda na Vercel. Se existir um projeto
> "backend" na Vercel apontando para este repositório, delete-o
> (Settings → Advanced → Delete Project) — é ele que gera o ❌ de
> "Deployment has failed" nos commits/PRs. FastAPI ali exigiria Postgres
> externo, filesystem em /tmp e sofreria com timeout de função; a VM não
> tem essas limitações.

O backend fala com o DocuSeal por três variáveis
(`backend/app/config.py` e `backend/app/routers/docuseal.py`):

| Variável | Para quê |
| --- | --- |
| `DOCUSEAL_API_KEY` | Token enviado no header `X-Auth-Token` em toda chamada à API |
| `DOCUSEAL_BASE_URL` | Base da API — já definida no compose como `http://docuseal:3000/api` (rede interna) |
| `DOCUSEAL_WEBHOOK_SECRET` | Valida o header `X-Docuseal-Secret` do webhook. **Sem ela o webhook responde 403 sempre** e o contrato nunca muda para "assinado" |

## 1. Subir o stack na VM

Pré-requisitos: VM com Docker e dois DNS apontados para ela, ex.:
`api.carvalhofurtadoadv.com.br` e `docuseal.carvalhofurtadoadv.com.br`.

```bash
git clone <repo> && cd Honorario-cf/deploy
cp .env.example .env               # domínios, SECRET_KEY_BASE, senha Postgres, SMTP
cp backend.env.example backend.env # Azure, CORS, e depois a API key do DocuSeal
docker compose up -d --build
```

O Caddy emite os certificados HTTPS sozinho. O SMTP do `.env` é
obrigatório — é por ele que o DocuSeal envia os convites de assinatura.

## 2. Obter a API key do DocuSeal

1. Acesse `https://<DOCUSEAL_HOST>` e crie a conta de administrador
   (primeiro acesso).
2. Menu **Settings → API** → copie o token.
3. Coloque em `DOCUSEAL_API_KEY` no `deploy/backend.env` e gere um
   `DOCUSEAL_WEBHOOK_SECRET` (`openssl rand -hex 32`).
4. `docker compose up -d backend` para recarregar.

*(Alternativa sem Docker: a nuvem DocuSeal em `https://api.docuseal.com`
exige plano pago; a chave fica no console em Settings → API e
`DOCUSEAL_BASE_URL` precisa ser sobrescrita no compose.)*

## 3. Configurar o webhook (status "assinado")

No DocuSeal: **Settings → Webhooks → Add webhook**

- **URL**: `https://<API_HOST>/api/docuseal/webhook`
- **Secret header**: nome `X-Docuseal-Secret`, valor igual ao
  `DOCUSEAL_WEBHOOK_SECRET` do `backend.env`
- **Eventos**: `submission.completed` e `submission.declined`

## 4. Apontar o frontend (Vercel) para a VM

No projeto `honorario-cf` da Vercel → **Settings → Environment Variables**:

```
NEXT_PUBLIC_API_URL=https://<API_HOST>
```

e faça um redeploy do frontend.

## 5. Validar

```bash
# Backend de pé
curl https://<API_HOST>/api/health

# API do DocuSeal respondendo com a chave (de dentro da VM)
docker compose exec backend python -c "import os,urllib.request; r=urllib.request.Request('http://docuseal:3000/api/templates', headers={'X-Auth-Token': os.environ['DOCUSEAL_API_KEY']}); print(urllib.request.urlopen(r).status)"

# Webhook recusando chamada sem secret (deve retornar 403)
curl -X POST https://<API_HOST>/api/docuseal/webhook \
  -H "Content-Type: application/json" -d '{"event_type":"ping","data":{}}'
```

Depois, gere um contrato de teste e envie para assinatura; ao concluir
todas as assinaturas, o status deve mudar para "assinado" via webhook
(auditoria `webhook_assinado` na página do contrato).

## Backup

Volumes com dados: `contratos_data` (DOCX gerados), `postgres_backend_data`
(contratos/participações), `docuseal_data` e `postgres_docuseal_data`.

```bash
docker compose exec postgres-backend pg_dump -U honorario honorario > honorario-$(date +%F).sql
docker compose exec postgres-docuseal pg_dump -U docuseal docuseal > docuseal-$(date +%F).sql
```
