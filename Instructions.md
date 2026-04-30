Você está retomando um projeto de automação de contratos de honorários advocatícios que foi iniciado por outra IA (Devin) e interrompido na tarefa 5 de 10. O repositório completo já está em F:\Users\Paollo\Codigo\repo. Seu trabalho é examinar o que foi feito, corrigir eventuais duplicidades, integrar frontend e backend, e implementar as funcionalidades restantes para que o sistema funcione ponta a ponta.

## Contexto do projeto

O sistema é um assistente (wizard) que guia um advogado no preenchimento de um contrato de honorários. As respostas do advogado substituem campos pré-definidos (em vermelho no modelo original) e geram cláusulas automaticamente. Após preenchimento, o contrato final é enviado por email (via Azure/Outlook) para conferência e, depois de confirmado, encaminhado para assinatura digital no DocuSeal.

Fluxo completo:
1. Advogado acessa o wizard (frontend Next.js) e responde perguntas em 7 etapas:
   - Etapa 1: Qualificação do contratante (PJ ou PF)
   - Etapa 2: Delimitação do objeto e escopo (com escopos pré-definidos + campo aberto)
   - Etapa 3: Honorários (tipos cumulativos: hora, prolabore, mensalidade, êxito, permuta)
   - Etapa 4: Acessórios (reembolso, penalidades)
   - Etapa 5: Participações internas (ficha anexa não exibida ao cliente)
   - Etapa 6: Revisão dos dados preenchidos
   - Etapa 7: Envio (confirmação e disparo)
2. Backend (FastAPI) recebe os dados, gera o contrato substituindo placeholders no modelo .docx, envia o PDF por email usando Azure Email Communication Service.
3. Após confirmação do cliente, o advogado aciona o envio para assinatura via DocuSeal.

Tecnologias obrigatórias:
- Frontend: Next.js (já iniciado)
- Backend: FastAPI (já iniciado)
- Email: Azure Communication Services (obrigatório)
- Assinatura digital: DocuSeal (obrigatório)
- Modelo de contrato: arquivo .docx (já presente: "2026 Contrato de Honorários Modelo Padrão.docx")

## Estado atual do projeto (baseado nos arquivos criados)

### Estrutura de diretórios (raiz do repo)
- `backend/` (ou similar): contém os arquivos Python
  - `main.py`
  - `config.py`
  - `contract.py`
  - `contract_generator.py`
  - `docuseal.py` (dois arquivos com esse nome, possivelmente em subpastas diferentes – verificar)
  - `email.py`
  - `azure_email.py`
  - `currency.py`
  - `cnpj.py` (provavelmente integração com API da Receita Federal)
  - `__init__.py` (vários)
- `frontend/` (Next.js):
  - `src/app/layout.tsx`
  - `src/app/page.tsx`
  - `src/app/globals.css`
  - Componentes: `ContractWizard.tsx`, `FormField.tsx`, `StepIndicator.tsx`, `Step1Contratante.tsx`, `Step2Escopo.tsx`, `Step3Honorarios.tsx`, `Step4Acessorios.tsx`, `Step5Participacao.tsx`, `Step6Revisao.tsx`, `Step7Envio.tsx`, `Step9Indicador.tsx` (há um Step9, Step8 ausente)
  - `api.ts` (cliente HTTP)
  - `.env.local` (variáveis de ambiente)
- Arquivos de configuração: `pyproject.toml`, `.env.example`, `.gitignore`

### Progresso provável
- Backend: APIs básicas definidas (`main.py`), módulo de contrato (`contract.py`), gerador de contratos (`contract_generator.py`), integração Azure (`azure_email.py`), integração DocuSeal (`docuseal.py`), utilitários (`currency.py`, `cnpj.py`). Provavelmente tudo está esboçado, mas pode não estar completamente integrado ou testado.
- Frontend: todos os componentes do wizard foram criados, mas podem não estar conectados a uma API real ou ter a lógica de "contexto inteligente" implementada (a descrição menciona perguntas de refinamento, subitens condicionais, etc., que podem estar faltando).
- O Devin parou durante a etapa 5/10 ("Build the frontend: smart questionnaire with intelligent context system") logo após criar os componentes, mas sem concluir a integração total.

## Tarefas a realizar (em ordem)

1. Analise o código existente:
   - Leia todos os arquivos Python do backend, especialmente `main.py`, `contract_generator.py`, `azure_email.py`, `docuseal.py` e `config.py`.
   - Leia todos os componentes React do frontend.
   - Identifique funcionalidades já implementadas, placeholders e inconsistências (ex.: dois `docuseal.py`, ausência de Step8, possíveis duplicidades de contratos).
   - Verifique se as variáveis de ambiente necessárias estão listadas em `.env.example`.

2. Corrija e organize:
   - Se houver dois arquivos `docuseal.py`, mescle-os ou mantenha apenas o mais completo, corrigindo imports.
   - Garanta que todos os endpoints necessários estejam definidos em `main.py` e que correspondam às chamadas do frontend (`api.ts`).
   - Remova arquivos duplicados e organize a estrutura de diretórios de forma clara (ex.: backend em `backend/` e frontend em `frontend/`).

3. Implemente o "contexto inteligente" (perguntas dinâmicas):
   - O wizard deve gerar perguntas de refinamento baseadas nas respostas do advogado. Ex.: ao selecionar "Consultoria e contencioso nas áreas de atuação do C&F", surgem subitens para detalhar. Ao marcar "Hora trabalhada", exibir campos de teto mensal, pacote de horas, urgência, etc.
   - Os componentes `Step1` a `Step7` já contêm a lógica básica de exibição condicional? Se não, adicione a lógica para mostrar/ocultar campos de acordo com as seleções.
   - Certifique-se de que os dados coletados respeitem a estrutura esperada pelo backend (contrato de honorários).

4. Conecte frontend ao backend:
   - Atualize `api.ts` (ou crie) para chamar os endpoints da API FastAPI (por exemplo, `/api/generate-contract`, `/api/send-email`, `/api/send-docusign`).
   - No Step7 (Envio), implemente a ação de enviar os dados do formulário para o backend, que deve gerar o contrato (substituindo os campos), retornar uma prévia ou enviar diretamente por email.
   - Trate estados de loading e erro.

5. Finalize a geração de contrato:
   - O módulo `contract_generator.py` deve abrir o modelo .docx, localizar os placeholders (campos em vermelho, provavelmente marcados com chaves ou texto especial) e substituir pelas respostas do advogado, incluindo valores por extenso entre parênteses.
   - Gere um PDF ou mantenha .docx para anexo no email.
   - Teste com dados simulados.

6. Implemente o envio de email via Azure:
   - Complete `azure_email.py` para usar a Azure Communication Services Email API (chave de conexão no .env).
   - Envie o contrato gerado como anexo para o endereço de email do contratante (obtido no passo 1) e uma cópia para o advogado.
   - O corpo do email deve solicitar conferência.

7. Implemente a integração com DocuSeal:
   - Complete `docuseal.py` para criar um envelope de assinatura, adicionar o documento e os signatários (contratante e advogado), e enviar o link de assinatura.
   - Essa etapa deve ser acionada após a confirmação do email (talvez um webhook ou ação manual do advogado, como um botão "Enviar para assinatura" que chama o backend).

8. Teste o fluxo completo:
   - Execute o backend e frontend localmente.
   - Simule o preenchimento de todas as etapas, gere um contrato, envie o email (pode usar um email de teste) e dispare a assinatura (ambiente sandbox do DocuSeal).
   - Corrija bugs e ajustes de usabilidade.

9. Documente o projeto:
   - Atualize o README com instruções de instalação, variáveis de ambiente necessárias e como rodar.
   - Garanta que o `.env.example` contenha todas as chaves requeridas: `AZURE_EMAIL_CONNECTION_STRING`, `DOCUSEAL_API_KEY`, `DOCUSEAL_API_URL`, `RECEITA_FEDERAL_API_KEY`, etc.

## Instruções específicas para o Claude Code

- Ao ler o código, sempre use as ferramentas de busca e leitura de arquivos do VS Code (ou prompt "Read file: ...").
- Forneça atualizações periódicas do progresso, resumindo o que foi alterado.
- Se encontrar decisões de design não documentadas, tome a decisão mais razoável e documente-a em comentários ou no README.
- Priorize fazer a aplicação funcionar ponta a ponta, mesmo que inicialmente com dados simulados, antes de refinar detalhes visuais ou de UX.
- Mantenha a consistência com o que já foi implementado; não reescreva tudo a menos que seja estritamente necessário.

Ambiente:
- VS Code aberto no diretório `F:\Users\Paollo\Codigo\repo`
- Backend: Python 3.11+, gerenciado com Poetry (conforme `pyproject.toml`)
- Frontend: Node.js 20+, Next.js 14+

Comece analisando a estrutura atual do repositório e me diga o que encontrou.