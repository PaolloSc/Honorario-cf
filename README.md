# Automacao de Contratos de Honorarios - C&F Advogados

Sistema para automacao de contratos de honorarios advocaticios com geracao dinamica de documentos, envio por e-mail via Azure/Outlook e assinatura digital via DocuSeal.

## Arquitetura

- **Frontend**: Next.js 14+ (App Router) + TypeScript + Tailwind CSS v4
- **Backend**: FastAPI (Python) + python-docx
- **Email**: Microsoft Graph API (Azure AD) - Outlook
- **Assinatura Digital**: DocuSeal API
- **Modelo**: arquivo .docx (contrato de honorarios)

## Fluxo

1. Advogado acessa o wizard e preenche o formulario inteligente em 7 etapas:
   - Etapa 1: Qualificacao do contratante (PF ou PJ) - com consulta CNPJ automatica
   - Etapa 2: Delimitacao do objeto e escopo (com Contexto Inteligente)
   - Etapa 3: Honorarios (tipos cumulativos: hora, prolabore, mensalidade, sucesso, permuta)
   - Etapa 4: acessorios (reembolso, penalidades)
   - Etapa 5: Participacoes internas (ficha nao exibida ao cliente)
   - Etapa 6: Revisao dos dados
   - Etapa 7: Envio (geracao, email e assinatura)
2. Backend gera o contrato substituindo placeholders no modelo .docx
3. Contrato enviado por email via Microsoft Graph API (Outlook)
4. Apos confirmacao, documento enviado para assinatura digital via DocuSeal

## Requisitos

- Python 3.11+
- Node.js 20+
- Azure AD App (para envio de emails)
- DocuSeal API Key

## Instalacao

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
# Editar .env com suas credenciais
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Variaveis de Ambiente

### Backend (.env)

```env
# Azure AD / Microsoft Graph API
AZURE_TENANT_ID=seu-tenant-id
AZURE_CLIENT_ID=seu-client-id
AZURE_CLIENT_SECRET=seu-client-secret
AZURE_SENDER_EMAIL=seu-email@outlook.com

# DocuSeal API
DOCUSEAL_API_KEY=sua-api-key
DOCUSEAL_BASE_URL=https://api.docuseal.com

# App settings
CORS_ORIGINS=http://localhost:3000
TEMPLATE_PATH=templates/timbrado_peticao_1.dotx
OUTPUT_DIR=generated_contracts
```

O backend ja vem configurado para usar o modelo timbrado em
`backend/templates/timbrado_peticao_1.dotx`. Esse modelo segue o Manual de
Padronizacao de Documentos do escritorio: margens 3cm/3cm/2cm/2cm, fonte
Segoe UI 12, titulos em maiusculo e negrito, espacamento 1,15 no texto e 6pt
entre paragrafos.

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## API Endpoints

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | /api/health | Health check |
| POST | /api/contract/generate | Gerar contrato |
| GET | /api/contract/{id}/download | Baixar contrato |
| POST | /api/email/send | Enviar email com contrato |
| POST | /api/docuseal/send-for-signature | Enviar para assinatura |
| GET | /api/cnpj/{cnpj} | Consultar dados do CNPJ |

## Escopos Disponiveis

- `consultoria_contencioso_geral`: Consultoria e contencioso geral
- `contencioso_representacao`: Contencioso para representacao judicial
- `contencioso_memoriais`: Contencioso para memoriais e sustentacao oral
- `contencioso_tutela_urgencia`: Contencioso para tutela de urgencia
- `consultoria_lgpd`: Consultoria LGPD
- `consultoria_compliance_trabalhista`: Compliance Trabalhista
- `consultoria_planejamento_tributario`: Planejamento tributario
- `consultoria_diagnostico_fiscal`: Diagnostico fiscal
- `consultoria_planejamento_patrimonial`: Planejamento patrimonial
- `consultoria_estruturacao_societaria`: Estruturacao societaria
- `consultoria_contratual`: Analise contratual
- `consultoria_elaboracao_documentos`: Elaboracao de documentos
- `consultoria_opiniao_legal`: Opinjao legal / parecer
- `outro`: Escopo customizado

## Tipos de Honorario

- **hora_trabalhada**: Com teto mensal, pacote de horas, urgencia (+50%), fora do expediente (+100%)
- **pro_labore**: A vista ou parcelado
- **mensalidade**: Advocacia de partido, por processo ou por pasta, com variacao de preco
- **exito**: Percentual fixo ou variavel, beneficio prospectivo, deducao de outro honorario
- **permuta**: Com ou sem torna

## Contexto Inteligente

O wizard exibe campos adicionais baseados nas selecoes:

- Ao selecionar "Contencioso representacao": exibe campos para numero dos autos e demandas
- Ao selecionar "Contencioso memoriais": exibe campos para atividades (memoriais, sustentacao oral)
- Ao selecionar "Planejamento patrimonial": exibe campo para pessoas/patrimonios
- Ao selecionar "Estruturacao societaria": exibe campo para tipo de restruturacao
- Cada tipo de honorario exibe campos especificos quando selecionado

## Desenvolvimento

### Estrutura de diretorios

```
repo/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Configuracoes
│   │   ├── models/
│   │   │   └── contract.py   # Modelos Pydantic
│   │   ├── routers/
│   │   │   ├── contract.py   # Geracao de contrato
│   │   │   ├── email.py      # Envio de email
│   │   │   ├── docuseal.py   # Assinatura digital
│   │   │   └── cnpj.py       # Consulta CNPJ
│   │   ├── services/
│   │   │   ├── contract_generator.py
│   │   │   ├── azure_email.py
│   │   │   └── docuseal.py
│   │   └── utils/
│   │       └── currency.py
│   ├── pyproject.toml
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx
    │   │   └── globals.css
    │   ├── components/
    │   │   ├── ContractWizard.tsx
    │   │   ├── ui/
    │   │   │   ├── FormField.tsx
    │   │   │   └── StepIndicator.tsx
    │   │   └── steps/
    │   │       ├── Step1Contratante.tsx
    │   │       ├── Step2Escopo.tsx
    │   │       ├── Step3Honorarios.tsx
    │   │       ├── Step4Acessorios.tsx
    │   │       ├── Step5Participacao.tsx
    │   │       ├── Step6Revisao.tsx
    │   │       └── Step7Envio.tsx
    │   ├── types/
    │   │   └── contract.ts
    │   └── app/
    │       └── lib/
    │           └── api.ts
    └── package.json
```

### Status atual

- Backend: Implementado e funcional (FastAPI + python-docx)
- Frontend: Implementado com wizard de 7 etapas (Next.js 15 + Tailwind CSS v4)
- Integracao: Conectada via API client (`api.ts`)
- Configuracao: `page.tsx`, `tsconfig.json`, `next.config.ts`, `postcss.config.js` criados

### Pendencias

- Preencher credenciais reais em `backend/.env` (Azure AD e DocuSeal)
- Testar fluxo completo com credenciais reais
- Opcional: adicionar autenticacao no frontend para proteger o wizard
