# DocuSeal em produção — API key e configuração

O backend fala com o DocuSeal por três variáveis de ambiente
(`backend/app/config.py` e `backend/app/routers/docuseal.py`):

| Variável | Para quê |
| --- | --- |
| `DOCUSEAL_API_KEY` | Token enviado no header `X-Auth-Token` em toda chamada à API |
| `DOCUSEAL_BASE_URL` | Base da API (nuvem ou instância própria) |
| `DOCUSEAL_WEBHOOK_SECRET` | Valida o header `X-Docuseal-Secret` do webhook. **Sem ela o webhook responde 403 sempre** e o contrato nunca muda para "assinado" |

Há duas formas de ter API key em produção:

## Opção A — Nuvem DocuSeal (sem Docker)

A API da nuvem exige plano pago (Pro). Se for esse o caminho:

1. Console em <https://console.docuseal.com> → **Settings → API** → copiar a chave.
2. No ambiente do backend:

   ```
   DOCUSEAL_API_KEY=<chave do console>
   DOCUSEAL_BASE_URL=https://api.docuseal.com
   ```

## Opção B — Auto-hospedado via Docker (recomendado)

A versão self-hosted tem API completa sem custo por assinatura. Os arquivos
estão em `deploy/docuseal/`.

### 1. Subir o servidor

Em uma VM com Docker e um domínio apontado para ela (ex.:
`docuseal.carvalhofurtadoadv.com.br`):

```bash
cd deploy/docuseal
cp .env.example .env      # preencher HOST, SECRET_KEY_BASE, POSTGRES_PASSWORD e SMTP
docker compose up -d
```

O Caddy emite o certificado HTTPS sozinho. O SMTP é obrigatório — é por ele
que o DocuSeal envia os convites de assinatura aos signatários.

### 2. Obter a API key

1. Acesse `https://<HOST>` e crie a conta de administrador (primeiro acesso).
2. Menu **Settings → API** → copie o token (`X-Auth-Token`).

### 3. Configurar o backend

No ambiente de produção do backend (Railway/Render/etc.):

```
DOCUSEAL_API_KEY=<token do passo 2>
DOCUSEAL_BASE_URL=https://<HOST>/api
DOCUSEAL_WEBHOOK_SECRET=<string aleatória, ex.: openssl rand -hex 32>
```

Atenção ao `/api` no final da `DOCUSEAL_BASE_URL` — na nuvem a base é
`https://api.docuseal.com`, mas no self-hosted a API fica sob o caminho
`/api` do próprio domínio.

### 4. Configurar o webhook (status "assinado")

No DocuSeal: **Settings → Webhooks → Add webhook**

- **URL**: `https://<backend>/api/docuseal/webhook`
- **Secret header**: nome `X-Docuseal-Secret`, valor igual ao
  `DOCUSEAL_WEBHOOK_SECRET` do backend
- **Eventos**: `submission.completed` e `submission.declined`

### 5. Validar

```bash
# API respondendo com a chave
curl -H "X-Auth-Token: $DOCUSEAL_API_KEY" https://<HOST>/api/templates

# Webhook do backend recusando chamada sem secret (deve ser 403)
curl -X POST https://<backend>/api/docuseal/webhook \
  -H "Content-Type: application/json" -d '{"event_type":"ping","data":{}}'
```

Depois, gerar um contrato de teste e enviar para assinatura; ao concluir
todas as assinaturas, o status na plataforma deve mudar para "assinado"
via webhook (auditoria `webhook_assinado` na página do contrato).

## Backup (self-hosted)

Os dados ficam nos volumes `docuseal_data` (arquivos/assinaturas) e
`postgres_data` (banco). Exemplo de dump diário:

```bash
docker compose exec postgres pg_dump -U docuseal docuseal > docuseal-$(date +%F).sql
```
