# Automação de Contratos de Honorários — C&F Advogados

[![Next.js](https://img.shields.io/badge/Next.js-14+-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Azure AD](https://img.shields.io/badge/Azure_AD-0078D4?style=flat-square&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![DocuSeal](https://img.shields.io/badge/DocuSeal-assinatura_digital-6366F1?style=flat-square)](https://docuseal.com)
[![CI](https://github.com/PaolloSc/Honorario-cf/actions/workflows/ci.yml/badge.svg)](https://github.com/PaolloSc/Honorario-cf/actions/workflows/ci.yml)

Sistema para automação de contratos de honorários advocatícios com geração dinâmica de documentos, envio por e-mail via Azure/Outlook e assinatura digital via DocuSeal.

> **Stack:** Next.js 14 · FastAPI · python-docx · Microsoft Graph API · DocuSeal API · Tailwind CSS v4

## Arquitetura

| Camada | Tecnologia | Responsabilidade |
|--------|-----------|------------------|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind v4 | Wizard de 7 etapas, UX/UI |
| Backend | FastAPI (Python) + python-docx | Geração do `.docx`, endpoints REST |
| E-mail | Microsoft Graph API (Azure AD) | Envio via Outlook |
| Assinatura | DocuSeal API | Assinatura digital do contrato |
| Template | Arquivo `.docx` timbrado | Modelo oficial do escritório |

## Fluxo

1. Advogado acessa o wizard e preenche o formulário inteligente em 7 etapas:
   - **Etapa 1:** Qualificação do contratante (PF ou PJ) — com consulta CNPJ automática
   - **Etapa 2:** Delimitação do objeto e escopo (com Contexto Inteligente)
   - **Etapa 3:** Honorários (tipos cumulativos: hora, pró-labore, mensalidade, êxito, permuta)
   - **Etapa 4:** Acessórios (reembolso, penalidades)
   - **Etapa 5:** Participações internas (ficha não exibida ao cliente)
   - **Etapa 6:** Revisão dos dados
   - **Etapa 7:** Envio (geração, e-mail e assinatura)
2. Backend gera o contrato substituindo placeholders no modelo `.docx`
3. Contrato enviado por e-mail via Microsoft Graph API (Outlook)
4. Após confirmação, documento enviado para assinatura digital via DocuSeal

## Requisitos

- Python 3.11+
- Node.js 20+
- Azure AD App (para envio de e-mails)
- DocuSeal API Key

## Instalação

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

## Variáveis de Ambiente

### Backend (`.env`)

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

O backend já vem configurado para usar o modelo timbrado em
`backend/templates/timbrado_peticao_1.dotx`. Esse modelo segue o Manual de
Padronização de Documentos do escritório: margens 3cm/3cm/2cm/2cm, fonte
Segoe UI 12, títulos em maiúsculo e negrito, espaçamento 1,15 no texto e 6pt
entre parágrafos.

### Frontend (`.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/health` | Health check |
| POST | `/api/contract/generate` | Gerar contrato |
| GET | `/api/contract/{id}/download` | Baixar contrato |
| POST | `/api/email/send` | Enviar e-mail com contrato |
| POST | `/api/docuseal/send-for-signature` | Enviar para assinatura |
| GET | `/api/cnpj/{cnpj}` | Consultar dados do CNPJ |

## Escopos Disponíveis

| Código | Descrição |
|--------|-----------|
| `consultoria_contencioso_geral` | Consultoria e contencioso geral |
| `contencioso_representacao` | Contencioso para representação judicial |
| `contencioso_memoriais` | Contencioso para memoriais e sustentação oral |
| `contencioso_tutela_urgencia` | Contencioso para tutela de urgência |
| `consultoria_lgpd` | Consultoria LGPD |
| `consultoria_compliance_trabalhista` | Compliance Trabalhista |
| `consultoria_planejamento_tributario` | Planejamento tributário |
| `consultoria_diagnostico_fiscal` | Diagnóstico fiscal |
| `consultoria_planejamento_patrimonial` | Planejamento patrimonial |
| `consultoria_estruturacao_societaria` | Estruturação societária |
| `consultoria_contratual` | Análise contratual |
| `consultoria_elaboracao_documentos` | Elaboração de documentos |
| `consultoria_opiniao_legal` | Opinião legal / parecer |
| `outro` | Escopo customizado |

## Tipos de Honorário

- **hora_trabalhada** — Com teto mensal, pacote de horas, urgência (+50%), fora do expediente (+100%)
- **pro_labore** — À vista ou parcelado
- **mensalidade** — Advocacia de partido, por processo ou por pasta, com variação de preço
- **exito** — Percentual fixo ou variável, benefício prospectivo, dedução de outro honorário
- **permuta** — Com ou sem torna

## Contexto Inteligente

O wizard exibe campos adicionais baseados nas seleções:

- **Contencioso representação** → campos para número dos autos e demandas
- **Contencioso memoriais** → campos para atividades (memoriais, sustentação oral)
- **Planejamento patrimonial** → campo para pessoas/patrimônios
- **Estruturação societária** → campo para tipo de reestruturação
- Cada tipo de honorário exibe campos específicos quando selecionado

## Estrutura de Diretórios

```
repo/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Configurações
│   │   ├── models/
│   │   │   └── contract.py   # Modelos Pydantic
│   │   ├── routers/
│   │   │   ├── contract.py   # Geração de contrato
│   │   │   ├── email.py      # Envio de e-mail
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
    │   └── lib/
    │       └── api.ts
    └── package.json
```

## Status

- [x] Backend implementado e funcional (FastAPI + python-docx)
- [x] Frontend com wizard de 7 etapas (Next.js 15 + Tailwind CSS v4)
- [x] Integração backend/frontend via API client (`api.ts`)
- [ ] Credenciais reais em `backend/.env` (Azure AD e DocuSeal)
- [ ] Testes de fluxo completo com credenciais reais
- [ ] Autenticação no frontend para proteger o wizard
