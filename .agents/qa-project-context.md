# QA — contexto do projeto (Honorário C&F)

Lido pelas skills de QA. Só fatos observados em 2026-10-29; o que não se sabe fica em "Em aberto".

## O que é
Sistema interno do Carvalho & Furtado Advogados: monta contratos de honorários (wizard de 7 passos), documentos derivados (aditivo, distrato, substabelecimento) e envia para assinatura (DocuSeal). Repositório **público** `PaolloSc/Honorario-cf`, branch padrão `master`.

## Stack
- Frontend: Next.js 15 (App Router), React 19, Tailwind 4, next-auth v5 (Microsoft Entra + link de convidado `/convite/<token>`).
- Backend: FastAPI + SQLAlchemy; sqlite local, Postgres (Neon) em homolog/produção; geração de DOCX com python-docx.
- Hospedagem: Vercel (projetos `backend`, `honorario-cf`, `backend-homolog`, `frontend-homolog`).
- Integrações: DocuSeal (assinatura), Microsoft Graph (e-mail), Legal One (processos), DeepSeek (revisão por IA), NFS-e BH.

## Testes que existem
- Backend: pytest, ~830 testes (`backend/tests`, 64 arquivos); roda em ~3 min e compartilha um banco sqlite.
- Frontend: `npx tsc --noEmit` e 7 verificações `node src/app/lib/*.check.ts` (lógica pura, sem navegador).
- CI (`.github/workflows/ci.yml`): pytest + tsc + `next build`. **Não havia teste no navegador antes de `e2e/`.**

## Ambientes
| | Frontend | Backend | Dados |
|---|---|---|---|
| Local | `next dev` :3000 | `uvicorn` :8000 | sqlite |
| **Homolog** | projeto Vercel `frontend-homolog` (URL fixa da branch `homolog`) | projeto `backend-homolog` | Neon branch `homolog`, só dados fictícios |
| Produção | **proibido para testes** | — | dados reais de clientes |

Homolog roda a branch `homolog` (deploy automático por push) e pode estar **atrasado em relação ao `master`**: confira o commit antes de culpar um teste.

## Acesso para teste
- Entrada sem senha: `/convite/<token>` (admin do ambiente de teste). O token e as URLs do homolog vêm do ambiente (`E2E_TOKEN`, `E2E_FRONT`, `E2E_BACK`), **nunca do repositório**. Login Microsoft não é automatizado.
- Homolog: DocuSeal e Graph desligados ou com credencial inválida; nada deve ser enviado para assinatura nem por e-mail.

## Riscos (por ordem)
1. Texto jurídico errado no contrato/distrato (valor, extenso, cláusula solta).
2. Documento enviado para assinatura/e-mail real por engano.
3. Dado real ou segredo no repositório público.
4. Valor monetário lido errado no formulário (ex.: "4.000" como R$ 4,00).
5. Dados de cliente (CPF, endereço) ou erro de infraestrutura vazando em mensagem de erro.

## Em aberto
- Sem CI para o E2E (precisa de segredo de homolog e decisão de quem hospeda).
- Cobertura de PJ no wizard, Ficha de participação, consumidor e NFS-e: sem teste no navegador.
- Legal One real (partes pelo CNJ) só pode ser testado com credencial.
