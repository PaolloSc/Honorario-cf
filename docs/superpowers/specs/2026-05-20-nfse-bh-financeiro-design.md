# Design — NFS-e PBH no Honorario-cf (Financeiro)

- **Data:** 2026-05-20
- **Autor:** PaolloSc + Claude (brainstorming)
- **Status:** Aprovado p/ implementação
- **Escopo:** Adicionar ao Honorario-cf a capacidade do setor financeiro puxar NFS-e da Prefeitura de Belo Horizonte (BHISS Digital), parsear, casar com contratos existentes, gerar pagamentos na Participação e produzir relatório comparativo.

## 1. Objetivo

Automatizar o ciclo "contrato → emissão NFS-e → pagamento → participação" reduzindo trabalho manual do financeiro e fornecendo auditoria contínua entre faturado e contratado.

Funcionalidades alvo:

1. Registrar pagamento automaticamente na Participação quando NF é emitida.
2. Calcular base de Participação (captação/performance) a partir do valor líquido da NF.
3. Gerar relatório mensal: faturado x contratado x recebido por contrato/cliente.

Casamento NF↔contrato é híbrido: CNPJ do tomador + competência (primário) com fallback para identificador `#<contract_id>` na discriminação. Casos ambíguos vão para fila manual.

## 2. Abordagem escolhida

**Scraping headless Playwright + credencial PBH armazenada criptografada.** Sem certificado digital ICP-Brasil. Worker desacoplado roda no GitHub Actions; API permanece leve no Render.

Motivação:

- Escritório ainda não possui e-CNPJ A1; webservice ABRASF da PBH exige certificado ICP-Brasil.
- Scraping resolve hoje, com custo zero; quando o certificado for adquirido, basta substituir o cliente sem mexer no resto do fluxo.
- Worker no GitHub Actions evita esgotar memória do Render Web (Chromium ~500MB) e expõe credencial apenas durante a janela de execução do job.

## 3. Arquitetura

```
┌───────────────────────────────────────────────────────────┐
│  GitHub Actions (.github/workflows/nfse-sync.yml)         │
│  schedule: '0 6 * * *' (03:00 America/Sao_Paulo)          │
│  matrix: 1 job por CNPJ prestador ativo                   │
│  steps: checkout → setup-python → playwright install →    │
│         python -m backend.workers.nfse_scraper.run ...    │
│  secrets: NFSE_WORKER_TOKEN, HONORARIO_API_URL            │
│  artifacts: screenshots em falha (retain 7d)              │
└────────────────────────┬──────────────────────────────────┘
                         │ HTTPS Bearer token
                         ▼
┌───────────────────────────────────────────────────────────┐
│  honorario-cf-api (Render Web Starter)                    │
│  GET  /api/nfse/credenciais/{cnpj}   (worker only)        │
│  POST /api/nfse/ingest               (worker only)        │
│  GET  /api/nfse                      (financeiro/admin)   │
│  POST /api/nfse/{id}/vincular        (financeiro/admin)   │
│  GET  /api/nfse/health                  (público; só     │
│                                          retorna estado, │
│                                          sem credencial) │
│  POST /api/admin/credencial-pbh      (admin)              │
│  POST /api/nfse/sync                 (financeiro/admin —  │
│                                       opcional manual)    │
└───────────────────────────────────────────────────────────┘
```

### 3.1 Módulos backend

```
backend/app/
├── routers/
│   ├── nfse.py                # endpoints REST do financeiro/admin
│   └── nfse_internal.py       # endpoints chamados pelo worker
├── services/
│   ├── nfse_parser.py         # XML → NFSeData (defusedxml)
│   ├── nfse_matcher.py        # heurística CNPJ/CPF → discriminação → manual
│   ├── nfse_pagamento.py      # bridge p/ participation_calculator
│   ├── nfse_sync.py           # orquestrador interno
│   └── crypto.py              # AES-GCM (KEK em env)
├── models/
│   └── nfse.py                # SQLAlchemy + Pydantic schemas
├── workers/
│   └── nfse_scraper/
│       ├── run.py             # entrypoint CLI usado pelo GH Actions
│       ├── client.py          # Playwright BHISS client
│       └── selectors.py       # seletores CSS centralizados
└── alembic/                   # migrations
```

### 3.2 Frontend

- Nova aba em `/financeiro`: "Notas Fiscais" (lista + vincular manual + status sync).
- Tela admin `/admin/credenciais-pbh`: upload e gerenciamento de credenciais.
- Componentes em `frontend/src/components/nfse/`.

## 4. Modelo de dados

### 4.1 Tabelas novas (Alembic migration)

```sql
CREATE TABLE credencial_pbh (
  id              SERIAL PRIMARY KEY,
  cnpj_prestador  VARCHAR(14) NOT NULL,
  login_enc       BYTEA NOT NULL,
  senha_enc       BYTEA NOT NULL,
  nonce_login     BYTEA NOT NULL,
  nonce_senha     BYTEA NOT NULL,
  ativo           BOOLEAN NOT NULL DEFAULT TRUE,
  motivo_inativacao TEXT,
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  criado_por      VARCHAR(255) NOT NULL,
  atualizado_em   TIMESTAMPTZ,
  UNIQUE(cnpj_prestador)
);

CREATE TABLE nfse_recebidas (
  id                 SERIAL PRIMARY KEY,
  cnpj_prestador     VARCHAR(14) NOT NULL,
  numero             VARCHAR(40) NOT NULL,
  serie              VARCHAR(10),
  codigo_verificacao VARCHAR(40),
  competencia        DATE NOT NULL,
  data_emissao       DATE NOT NULL,
  tomador_doc        VARCHAR(14) NOT NULL,    -- CPF ou CNPJ, só dígitos
  tomador_nome       TEXT,
  valor_servicos     NUMERIC(12,2) NOT NULL,
  iss_retido         NUMERIC(12,2) NOT NULL DEFAULT 0,
  irrf               NUMERIC(12,2) NOT NULL DEFAULT 0,
  pis                NUMERIC(12,2) NOT NULL DEFAULT 0,
  cofins             NUMERIC(12,2) NOT NULL DEFAULT 0,
  csll               NUMERIC(12,2) NOT NULL DEFAULT 0,
  valor_liquido      NUMERIC(12,2) NOT NULL,
  discriminacao      TEXT,
  cancelada          BOOLEAN NOT NULL DEFAULT FALSE,
  data_cancelamento  TIMESTAMPTZ,
  xml_raw            BYTEA NOT NULL,
  contract_id        VARCHAR(36) REFERENCES contracts(id),
  participacao_id    INTEGER REFERENCES participacoes(id),
  pagamento_id       INTEGER REFERENCES pagamentos(id),
  status_matching    VARCHAR(20) NOT NULL,    -- auto|manual|pendente|sem_match|erro|cancelada
  motivo             TEXT,
  criado_em          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em      TIMESTAMPTZ,
  UNIQUE(cnpj_prestador, numero, serie)
);

CREATE INDEX idx_nfse_status ON nfse_recebidas(status_matching);
CREATE INDEX idx_nfse_tomador ON nfse_recebidas(tomador_doc, competencia);
CREATE INDEX idx_nfse_contract ON nfse_recebidas(contract_id);

CREATE TABLE sync_jobs (
  id                SERIAL PRIMARY KEY,
  cnpj_prestador    VARCHAR(14) NOT NULL,
  origem            VARCHAR(20) NOT NULL,     -- cron|manual|workflow_dispatch
  disparado_por     VARCHAR(255),
  iniciado_em       TIMESTAMPTZ NOT NULL,
  finalizado_em     TIMESTAMPTZ,
  periodo_inicio    DATE NOT NULL,
  periodo_fim       DATE NOT NULL,
  total_nfs         INTEGER NOT NULL DEFAULT 0,
  auto_vinculadas   INTEGER NOT NULL DEFAULT 0,
  pendentes         INTEGER NOT NULL DEFAULT 0,
  sem_match         INTEGER NOT NULL DEFAULT 0,
  erros             INTEGER NOT NULL DEFAULT 0,
  status            VARCHAR(30) NOT NULL,     -- ok|erro_login|captcha|layout|portal_down|ja_rodando|erro
  motivo_falha      TEXT,
  screenshot_url    TEXT
);

CREATE TABLE nfse_audit_log (
  id            SERIAL PRIMARY KEY,
  nfse_id       INTEGER REFERENCES nfse_recebidas(id),
  credencial_id INTEGER REFERENCES credencial_pbh(id),
  acao          VARCHAR(50) NOT NULL,         -- credencial.create|credencial.disable|nfse.vincular_manual|nfse.cancelar|sync.start|sync.end
  user_email    VARCHAR(255),
  payload_before JSONB,
  payload_after  JSONB,
  ts            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Imutável: revogar UPDATE/DELETE via grants no Postgres.
```

### 4.2 Pydantic — `NFSeData`

```python
class NFSeData(BaseModel):
    cnpj_prestador: str
    numero: str
    serie: Optional[str] = None
    codigo_verificacao: Optional[str] = None
    competencia: date
    data_emissao: date
    tomador_doc: str            # CPF/CNPJ só dígitos
    tomador_nome: Optional[str] = None
    valor_servicos: Decimal
    iss_retido: Decimal = Decimal("0")
    irrf: Decimal = Decimal("0")
    pis: Decimal = Decimal("0")
    cofins: Decimal = Decimal("0")
    csll: Decimal = Decimal("0")
    discriminacao: Optional[str] = None
    cancelada: bool = False
    data_cancelamento: Optional[datetime] = None
    xml_raw: bytes

    @computed_field
    @property
    def valor_liquido(self) -> Decimal:
        return self.valor_servicos - self.iss_retido - self.irrf - self.pis - self.cofins - self.csll
```

## 5. Fluxo de execução

```
[GitHub Actions cron 06:00 UTC] OU [POST /api/nfse/sync]
   ↓
worker.run(cnpj_prestador):
   1. GET /api/nfse/credenciais/{cnpj} (Bearer token)
      → recebe {login, senha} HTTPS
   2. Playwright chromium headless
   3. login portal PBH
      ├─ falhou → POST /api/nfse/ingest {status:erro_login}; sai
      └─ CAPTCHA visível → POST {status:captcha_blocked}; sai
   4. determinar período:
      - última sync_jobs.periodo_fim + 1 dia até hoje
      - se nenhuma sync prévia: hoje - NFSE_BACKFILL_DAYS (default 90)
   5. navega menu "Consulta NFS-e Emitidas"
   6. filtra período, exporta XML lote
   7. parseia XMLs c/ defusedxml + valida XSD ABRASF
   8. POST /api/nfse/ingest { cnpj, periodo, xmls: [bytes...] }
      ↓
API.ingest():
   para cada XML:
     - parse → NFSeData
     - upsert nfse_recebidas (ON CONFLICT cnpj+numero+serie DO UPDATE
                              SET cancelada, motivo IF cancelada=true)
     - se cancelada e tinha pagamento: alerta financeiro, NÃO reverte
     - se nova:
         matcher.match(nf, contratos_ativos_doc_tomador):
           - 1 contrato c/ competência válida → status=auto, contract_id set
           - N contratos + #id na discriminação → status=auto pelo id
           - N contratos ambíguos → status=pendente
           - 0 → status=sem_match
       se status=auto E contrato tem Participacao ativa:
         lock SELECT ... FOR UPDATE em nfse.id
         se pagamento_id IS NULL:
           registrarPagamento(participacao_id,
                              data=data_emissao,
                              valor_bruto=valor_servicos,
                              discriminado=True,
                              valor_contratual=valor_servicos)
           grava pagamento_id e participacao_id na NFSe
   finaliza sync_job c/ contagens
   envia email resumo p/ financeiro
```

## 6. Matcher — regras

Resolução de `cliente_doc`: contratos no Honorario-cf armazenam contratantes como lista `ContratantePF | ContratantePJ` (ver `backend/app/models/contract.py`). Antes do matcher rodar, o backend deriva um campo virtual `cliente_doc_normalizado` para cada contrato:

```
def cliente_doc(contrato) -> set[str]:
    docs = set()
    for c in contrato.contratantes:
        if isinstance(c, ContratantePF): docs.add(only_digits(c.cpf))
        if isinstance(c, ContratantePJ): docs.add(only_digits(c.cnpj))
    return docs
```

Match ocorre se `nf.tomador_doc in cliente_doc(contrato)`. Implementação cacheia em coluna materializada `contracts.cliente_docs` (JSON array) atualizada via trigger / signal no save do contrato.

```
Entrada: NFSeData nf, lista contratos onde:
  nf.tomador_doc IN contrato.cliente_docs
  contrato.data_inicio <= nf.competencia
  (contrato.data_fim IS NULL OR contrato.data_fim >= nf.competencia)

Decisão:
  candidatos = filtrados acima
  se len(candidatos) == 0:
    return sem_match
  se len(candidatos) == 1:
    return auto(candidato[0])
  # >1 candidato
  ids_descobertos = regex_find_ids(nf.discriminacao)
  matches_pelo_id = [c for c in candidatos if c.id.lower() in ids_descobertos]
  se len(matches_pelo_id) == 1:
    return auto(matches_pelo_id[0])
  return pendente(candidatos)
```

Regex discriminação: `r'#?\b([a-f0-9-]{8,36})\b'` aplicado em `discriminacao.lower()` sem espaços extras.

## 7. Tratamento de erros

| Falha | Detecção | Ação |
|---|---|---|
| Login inválido / senha expirou | Playwright detecta msg erro / URL não muda | `credencial.ativo=false`, audit log, email admin |
| CAPTCHA | seletor CAPTCHA visível pós-login | job `status=captcha_blocked`, alerta financeiro, sem retry |
| Portal fora do ar | timeout navigation 30s OR 5xx | retry 3x backoff (30s, 2min, 5min); falha → job `erro_portal` |
| Layout mudou | seletor crítico count==0 | job `status=layout`, screenshot artifact, email dev+admin |
| XML malformado | defusedxml raise | NF `status_matching=erro`, xml_raw preservado |
| NF duplicada | UNIQUE conflict | upsert atualiza só campos voláteis (cancelada, motivo) |
| Race matcher | lock SELECT FOR UPDATE + check `pagamento_id IS NULL` | 2º caller no-op |
| 2 syncs simultâneos | lock por `cnpj_prestador` (advisory lock pg / BEGIN IMMEDIATE sqlite) | 2º aborta `status=ja_rodando` |
| `registrarPagamento` valida e falha | service levanta | NF vinculada, `pagamento_id NULL`, motivo registrado, UI exibe aviso |

Retry policy:

- Cron: 1 retry imediato em falha de rede; senão deixa próximo dia.
- Manual: usuário decide.
- Nunca retenta auto: login, CAPTCHA, layout.

## 8. Segurança

### 8.1 Credenciais em repouso

- AES-GCM, KEK 32 bytes em `NFSE_KEK` (Render secret, GH Actions NÃO recebe KEK).
- Nonce 96 bits único por write (`os.urandom(12)`).
- `login_enc` e `senha_enc` armazenados separados com nonces distintos.
- Decrypt isolado em `services/crypto.py`; nunca logar plaintext.

### 8.2 Comunicação worker ↔ API

- Bearer token `NFSE_WORKER_TOKEN` (Render env + GH Secret).
- Endpoints `/api/nfse/credenciais/*` e `/api/nfse/ingest`:
  - exigem token,
  - IP allowlist com CIDR oficial do GitHub Actions (verificação em middleware).
- TLS obrigatório (Render garante).
- Token rotaciona por troca de env nas duas pontas.

### 8.3 Credencial em trânsito p/ worker

- API retorna JSON `{login, senha}` em resposta HTTPS, single use.
- Worker mantém em memória só durante o job; não persiste em disco.
- Logs do GH Actions têm masking ativo em vars que correspondem a secrets.

### 8.4 Rotação KEK

- Script `backend/scripts/rotate_kek.py`: lê todas linhas, decifra c/ KEK antigo (env `OLD_KEK`), recifra c/ novo (env `NEW_KEK`), grava.
- Runbook em `docs/runbooks/rotate-kek.md`.

### 8.5 Audit log imutável

- Tabela `nfse_audit_log` capturando: criação/inativação de credencial, sync start/end, vinculação manual, cancelamento detectado.
- Postgres: REVOKE UPDATE, DELETE em `nfse_audit_log`.
- SQLite (dev): trigger BEFORE UPDATE/DELETE que lança erro.

### 8.6 Permissões

- `/admin/credenciais-pbh` → `role IN ('admin')`.
- `/financeiro/notas-fiscais` lista, vincular, sync manual → `role IN ('financeiro','admin')`.
- `/api/nfse/ingest` e `/api/nfse/credenciais/*` → bearer worker only, nunca cookie de usuário.

### 8.7 Rate limit & DoS

- Lock por `cnpj_prestador` no sync.
- `slowapi` 5 req/min por user em `/api/nfse/sync`.
- Worker insere `random_delay(800-1500ms)` entre navegações no portal.

### 8.8 Sanitização XML

- `defusedxml` p/ todo parse (mitiga XXE).
- Validação XSD ABRASF antes de persistir; reject se inválido.

## 9. Timezone

- Toda lógica de datas usa `America/Sao_Paulo` via `zoneinfo.ZoneInfo`.
- Cron GH Actions em UTC: `0 6 * * *` = 03:00 SP (sem horário de verão atualmente vigente; revisar se restaurar DST).
- Colunas `*_em` armazenam `TIMESTAMPTZ` em UTC; conversão para SP só na apresentação.
- `competencia` e `data_emissao` são `DATE` interpretadas como calendário SP.

## 10. Frontend — UI

### 10.1 Aba `/financeiro/notas-fiscais`

```
┌─ Notas Fiscais ──────────────────────────────────────────────┐
│ [Sincronizar agora] [Mês: maio/2026 ▾] [Status: todos ▾]    │
│                                                               │
│ #1247  Cliente X SA   R$ 5.000  ✓ auto → Contrato #ab12cd34  │
│ #1248  Cliente Y      R$ 2.300  ⚠ pendente   [Vincular]      │
│ #1249  ???            R$   800  ✗ sem match                  │
│ #1250  Cliente X SA   R$ 1.000  🚫 cancelada                 │
│                                                               │
│ Resumo: 12 auto · 3 pendentes · 1 sem match · 2 canceladas   │
└──────────────────────────────────────────────────────────────┘
```

Modal "Vincular":

- Lista contratos do CNPJ/CPF do tomador com competência elegível.
- Seleção → confirma → gera audit log + tenta criar pagamento.

### 10.2 Tela `/admin/credenciais-pbh`

- Form: CNPJ prestador, login, senha (masked), ativo toggle.
- Lista credenciais com último sync, status, botão "desativar".
- Upload exige role=admin.

### 10.3 Health banner

- Se último `sync_jobs.status != 'ok'` há >36h: banner vermelho topo da aba.

## 11. Testes

### 11.1 Unit (pytest, sem rede)

```
backend/tests/
├── test_nfse_parser.py
│   - parse XML típico PBH → todos campos
│   - ISS retido > 0
│   - retenções federais (IRRF/PIS/COFINS/CSLL)
│   - PF tomador (CPF)
│   - NF cancelada → cancelada=True
│   - XML malformado → raise NFSeParseError
│   - XXE attack → defusedxml bloqueia
├── test_nfse_matcher.py
│   - 1 contrato CNPJ+competência → auto
│   - 2 contratos + #id discriminação → auto pelo id
│   - 2 contratos sem #id → pendente
│   - 0 contratos → sem_match
│   - contrato encerrado antes competência → ignora
│   - PF tomador → casa por CPF
│   - discriminação com espaços/maiúsculas → normaliza
├── test_crypto.py
│   - encrypt → decrypt roundtrip
│   - nonce errado → raise
│   - key errada → InvalidTag
│   - 2x encrypt same plaintext → nonces diferentes
├── test_nfse_pagamento.py
│   - NF vinculada → cria pagamento com valor_liquido correto
│   - lock impede 2 pagamentos p/ mesma NF
│   - participação inativa → vincula mas pagamento_id NULL
└── test_nfse_sync_orchestrator.py (scraper mockado)
    - 0 NFs → status=ok total=0
    - 10 NFs (8 auto + 2 pendente) → contagens corretas
    - CaptchaError → status=captcha_blocked, sem retry
    - LoginError → credencial.ativo=false, audit log, email
    - 2 chamadas concorrentes → 2ª = ja_rodando
    - idempotência: rodar 2x mesmo período não duplica
    - NF cancelada detectada → alerta, sem reversão
```

Cobertura alvo: parser/matcher/crypto ≥95%; sync ≥85%; scraper não medido (integration).

### 11.2 Integration (`@pytest.mark.integration`, opt-in)

```
backend/tests/integration/test_scraper_pbh_homolog.py
  - login c/ credencial homolog
  - navega menu consulta
  - filtra período pequeno
  - exporta XML lote → bytes não-vazios
```

- Env: `PBH_TEST_USER`, `PBH_TEST_PASS`.
- Workflow `nfse-integration.yml` noturno; skip se env ausente.
- Não bloqueia PR padrão.

### 11.3 Smoke E2E manual (`docs/qa/nfse-smoke.md`)

1. Admin sobe credencial homolog → confirmação verde.
2. Botão "Sincronizar agora" → job aparece.
3. NFs do mês listadas (≥1).
4. NF com contrato único → vinculada auto.
5. NF ambígua → vincular manual via modal → pagamento criado em `/financeiro`.
6. Forçar credencial errada → banner vermelho + email admin.
7. Detectar cancelamento → status na lista + alerta.

### 11.4 TDD enforcement

- Parser, matcher, crypto, pagamento_bridge: testes escritos antes do código (skill `superpowers:test-driven-development`).
- Scraper: cobertura via integration opt-in + smoke; implementação iterativa.

### 11.5 Fixtures

- `tests/fixtures/nfse/*.xml` — 8-10 XMLs reais anonimizados (PJ, PF, cancelada, com retenção, sem discriminação, com `#id`).
- `tests/fixtures/contratos.json` — casos cobrindo todas decisões do matcher.

## 12. Deploy

### 12.1 Backend (Render Web)

- `backend/requirements.txt` += `cryptography`, `defusedxml`, `lxml`, `slowapi`, `python-dateutil`, `tzdata`, `alembic`.
- Env novos:
  - `NFSE_ENABLED=false` (flag rollout)
  - `NFSE_KEK=<base64 32 bytes>`
  - `NFSE_WORKER_TOKEN=<random 48 chars>`
  - `NFSE_BACKFILL_DAYS=90`
  - `NFSE_GH_ACTIONS_CIDRS=<comma-separated, GH oficial>`
- Plano: Web Starter mantém (zero Chromium na API).

### 12.2 Migrations

- Adotar Alembic.
- Primeira migração cria: `credencial_pbh`, `nfse_recebidas`, `sync_jobs`, `nfse_audit_log` + grants imutáveis.
- Segunda migração adiciona em `contracts`: coluna `cliente_docs JSONB` (array de docs normalizados) + backfill via script lendo `contratantes`. Trigger/signal mantém atualizada em saves futuros.
- Rodada antes do deploy backend.

### 12.3 Worker (GitHub Actions)

`.github/workflows/nfse-sync.yml` (raiz do repo):

```yaml
name: nfse-sync
on:
  schedule:
    - cron: '0 6 * * *'    # 03:00 America/Sao_Paulo
  workflow_dispatch:
    inputs:
      periodo_inicio:
        required: false
      periodo_fim:
        required: false

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        cnpj: ${{ fromJSON(vars.PRESTADORES_CNPJS) }}
    env:
      HONORARIO_API_URL: ${{ secrets.HONORARIO_API_URL }}
      NFSE_WORKER_TOKEN: ${{ secrets.NFSE_WORKER_TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r backend/workers/nfse_scraper/requirements.txt
      - run: python -m playwright install --with-deps chromium
      - run: |
          python -m backend.workers.nfse_scraper.run \
            --cnpj ${{ matrix.cnpj }} \
            ${{ github.event.inputs.periodo_inicio && format('--inicio {0}', github.event.inputs.periodo_inicio) }} \
            ${{ github.event.inputs.periodo_fim && format('--fim {0}', github.event.inputs.periodo_fim) }}
      - if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: screenshots-${{ matrix.cnpj }}
          path: backend/workers/nfse_scraper/screenshots/
          retention-days: 7
```

Secrets: `HONORARIO_API_URL`, `NFSE_WORKER_TOKEN`.
Vars: `PRESTADORES_CNPJS` JSON array.

### 12.4 Frontend (Vercel)

- Novos componentes em `frontend/src/components/nfse/`.
- Novas rotas `/financeiro/notas-fiscais` e `/admin/credenciais-pbh`.
- Build padrão Next 15.

### 12.5 Feature flag

- `NFSE_ENABLED=false` em produção até smoke completo.
- Endpoints retornam 404 quando flag off.
- Worker no GH Actions verifica `/api/nfse/health` antes de rodar; se flag off, exit 0.

### 12.6 Rollout

1. Migrar DB (Alembic upgrade head).
2. Deploy backend com `NFSE_ENABLED=false`.
3. Deploy frontend.
4. Admin sobe credencial homolog PBH.
5. Smoke manual via `workflow_dispatch`.
6. Validar contagens no DB, pagamentos gerados.
7. Trocar `NFSE_ENABLED=true` em produção.
8. Aguardar primeiro cron (próxima madrugada).

## 13. Verification gate (antes de declarar pronto)

Implementação só é "pronta" se todos os abaixo passarem com evidência:

- Suíte unit verde (cobertura ≥ alvo).
- Integration opt-in verde contra homolog PBH.
- Smoke E2E manual completo, inclusive:
  - 1 sync diário simulado executado fim-a-fim;
  - ≥1 NF vinculada automaticamente;
  - ≥1 NF vinculada manualmente;
  - 1 NF cancelada detectada e alertada;
  - 1 erro de credencial reproduzido + email admin recebido.
- Audit log conferido (todas ações registradas).
- KEK rotation runbook testado em ambiente dev.

## 14. Fora de escopo (não fazer agora)

- Webservice ABRASF SOAP com certificado A1 (futuro; arquitetura permite trocar `nfse_scraper` por `nfse_ws` sem mexer no resto).
- Conciliação bancária (recebimento ≠ emissão de NF).
- Tomadores fora de BH (outras prefeituras).
- Exportação contábil (CSV/SPED) — pode entrar em iteração futura.
- Multi-tenant (cada escritório com sua base) — só C&F por enquanto.

## 15. Riscos abertos

| Risco | Mitigação |
|---|---|
| PBH altera layout do portal sem aviso | Integration noturno detecta; alerta dev. Mitigação definitiva = migrar p/ webservice quando cert chegar. |
| CAPTCHA introduzido na PBH | Plano B: 2Captcha API (custo ~R$0,01/resolução) ou pausa humana. Decidir quando ocorrer. |
| 2FA obrigatório na PBH | Sem solução automatizada; obriga migração p/ webservice + cert. |
| Senha do escritório expira sem aviso | `credencial.ativo=false` + email admin já tratam; financeiro re-cadastra. |
| GH Actions outage | Sync atrasa 1 ciclo; manual sempre disponível. |

## 16. Decisões integradas (referência)

| # | Item | Decisão |
|---|---|---|
| 1 | Migrations | Alembic |
| 2 | Backfill | `NFSE_BACKFILL_DAYS=90` |
| 3 | Cancelamento | detecta + alerta, sem reverter auto |
| 4 | PF/CPF | `tomador_doc` genérico |
| 5 | Competência | primary, fallback emissão |
| 6 | Race condition | SELECT FOR UPDATE + check `pagamento_id IS NULL` |
| 7 | Discriminação | regex normalizada |
| 8 | Cron | GitHub Actions |
| 9 | Worker | GH Actions (decoupled do Render) |
| 10 | Rate limit | lock por CNPJ + slowapi + delays |
| 11 | KEK rotation | script + runbook |
| 12 | Audit | `nfse_audit_log` imutável |
| 13 | Timezone | `America/Sao_Paulo` explícito |
| 14 | Multi-CNPJ | matrix GH Actions |
| 15 | NFSeData | schema definido |
| 16 | Worker decoupled | sim |
| 17 | `/ingest` endpoint | sim |
| 18 | `/health` | sim |
| 19 | TDD | enforced no plan |
| 20 | Verification | smoke checklist |