# Honorários C&F

Sistema que monta, revisa e envia para assinatura os contratos de honorários do escritório, a partir de um passo a passo (wizard) preenchido pelo advogado.

## Language

**Contrato**:
Documento de honorários de um cliente, com uma ou mais **Versões**. Só existe depois de gerado.
_Avoid_: Proposta, minuta

**Versão do contrato**:
Cada vez que o contrato é gerado ou salvo de novo na edição; guarda os dados exatos daquele momento.
_Avoid_: Revisão (reservado para a revisão por IA), histórico

**Dados do contrato**:
Tudo que o advogado informa e que o contrato (ou o envio dele) precisa para ser gerado, enviado ou retomado. É o que vai ao **Rascunho** e à **Versão**.
_Avoid_: Formulário, form_data (termo técnico)

**Dados de tela**:
O que só ajuda a preencher e se perde ao sair: busca digitada, resultado de consulta de CNPJ/CEP, listas carregadas. Nunca vai ao **Rascunho**.
_Avoid_: Estado local

**Estado do wizard**:
O conjunto único de **Dados do contrato** que todas as **Etapas** leem e alteram. Há uma só fonte; as etapas não guardam cópia própria.
_Avoid_: formData, estado das etapas

**Mensagem de erro segura**:
O que a API devolve quando algo falha: texto fixo, escrito para o usuário, sem o texto da exceção (que pode trazer CPF, nome, SQL ou resposta crua de terceiros). O detalhe técnico vai só para o log. Mensagens prontas em `backend/app/utils/erros.py`; o 500 não tratado vira `MSG_ERRO_INTERNO` em `main.py`.
_Avoid_: str(e) na resposta, detail com a exceção

**Pagamento de participação**:
Um recebimento de honorário e a participação que ele gera para o beneficiário. Nasce sempre em `pagamento_participacao.registrar`, seja digitado pelo financeiro ou vindo de uma NFS-e recebida: mesmas regras (imposto pelo tax code, limite temporal por tipo, fim do vínculo, corte de 31/07/2024). Só o rateio 50/50 de honorário não discriminado existe apenas no registro manual. Dinheiro em Decimal.
_Avoid_: Lançamento, repasse

## Passo a passo (wizard)

**Etapa**:
Uma das sete telas do wizard: Contratante, Escopo, Honorários, Acessórios, Ficha interna, Revisão, Envio.
_Avoid_: Passo, step

**Ficha interna**:
Etapa 5. Dados para o financeiro e para a participação (quem recebe parte dos honorários), não vão ao texto do contrato.
_Avoid_: Ficha de participação (é o registro criado a partir dela)

**Envio**:
Escolhas da etapa 7: e-mails dos contratantes, testemunhas e sócio que assina pelo escritório. Fazem parte dos **Dados do contrato**.
_Avoid_: Dados de envio

**Sócio que assina**:
Sócio do escritório que assina como Contratado. Se o advogado não escolher, o sistema sugere um.
_Avoid_: Assinante, signatário do escritório

## Rascunho e revisão

**Rascunho**:
Cópia automática dos **Dados do contrato** de um contrato em preenchimento ou em edição, guardada para retomar depois. Some quando o contrato é gerado.
_Avoid_: Contrato em rascunho (é o status de um contrato ainda não enviado)

**Retomar**:
Reabrir um **Rascunho** na etapa exata em que o advogado parou, inclusive a 7.
_Avoid_: Restaurar

**Revisão por IA**:
Conferência automática de português e padrão do texto gerado, feita na etapa 7.
_Avoid_: Revisão (sozinha)

**Revisão desatualizada**:
Estado da **Revisão por IA** e da **Prévia** quando os **Dados do contrato** mudaram depois da última revisão; precisam ser refeitas antes de gerar.
_Avoid_: Revisão antiga

**Prévia**:
Como o contrato ficará no Word/PDF, calculada a partir dos **Dados do contrato** atuais.

**Contrato carregado**:
Uma **Versão do contrato** salva já decodificada: tipo (honorários, consumidor aéreo, aditivo, distrato, substabelecimento), request validado, gerador e cliente. Vive em `backend/app/services/contrato_carregado.py`; download, e-mail, assinatura e reversão de versão usam só ele para remontar um contrato. Modo **brando** regera contratos antigos sem recusar; modo **estrito** (edição) aplica as regras do contrato novo.
_Avoid_: dispatch, parse do form_data

**Assinatura (envio)**:
Enviar a última **Versão do contrato** para assinatura no DocuSeal. É o caso de uso `enviar(db, contract_id, signatarios, user_email)` em `backend/app/services/assinatura.py`: sócio que assina pelo escritório, testemunha fixa, papéis únicos, ordem de assinatura, reenvio (arquiva a submissão anterior) e auditoria. A rota só traduz HTTP (`EnvioInvalido` → 400, `ArquivoNaoEncontrado` → 404). O DocuSeal entra pelo parâmetro `docuseal`, que é o seam dos testes.
_Avoid_: send_for_signature (nome da rota), submissão (é do DocuSeal)

**Documento (CPF/CNPJ)**:
O número de CPF ou CNPJ de uma parte, sempre comparado e guardado na forma normalizada de `backend/app/utils/documento.py` (`normalizar_doc`): sem pontuação, maiúsculo, **com** as letras do CNPJ alfanumérico. Todo módulo (contrato, distrato, substabelecimento, NFS-e, faturamento) usa essa função; não existe outra forma de "tirar a pontuação".
_Avoid_: so_digitos, limpar CNPJ (apaga letras)

**Capacidade**:
O que um papel (admin, advogado, financeiro, leitor) pode fazer: administrar, operar o financeiro, ler o financeiro, ver contratos de todos. A tabela papel → capacidades vive em `backend/app/acesso.py`; as rotas pedem a capacidade (`exigir(...)` / `pode(...)`) e nunca comparam o texto do papel.
_Avoid_: checar `user.role == "admin"` na rota

## Rede e erros

**Cliente HTTP**:
O único caminho do front para falar com a API: `frontend/src/app/lib/http.ts`. Uma base de URL (`API_BASE`), token renovado na hora da chamada, limite de tempo opcional por chamada (`timeoutMs`). `api.ts`, `emissao-api.ts`, `finance-api.ts`, `nfse-api.ts` e as páginas só chamam `chamarApi`/`chamarApiJson`; nenhuma tela faz `fetch` direto para a API.
_Avoid_: request, _fetch, pedir (eram os quatro clientes antigos)

**Erro por campo**:
422 de uma regra do contrato que diz qual campo falhou: o `loc` vem com o caminho do campo (ex.: `body.escopos.0.pro_labore.numero_parcelas`) e o `type` é `regra_contrato`. No backend sai de `_falha(loc, msg)` em `backend/app/models/contract.py` (hoje: regras de parcelamento do pró-labore e dos adicionais); no front, `errosPorCampo` em `frontend/src/app/lib/erro422.ts` devolve `{caminho: mensagem}`. Regra sem campo continua com `loc` só `body` e aparece pelo `textoDoErro`.
_Avoid_: ValueError sem campo para regra de um campo só, procurar o campo pelo texto da mensagem

**Erro da API**:
Resposta da API com status de erro. No front é sempre `ErroApi` (`status` + `corpo` cru), com a mensagem no formato `API error NNN: corpo`; o 409 é `ConflitoError`, o 401 sem sessão é `SessaoExpiradaError`. Falha de rede ou tempo esgotado não é Erro da API (não houve resposta).
_Avoid_: erro cru, HTTP error

## Endereço

**Busca de CEP**:
O único ponto do front que consulta o ViaCEP: `buscarCep` em `frontend/src/app/lib/endereco.ts`. Devolve rua, bairro, cidade e UF (campo ausente vira ""), `null` quando o CEP não existe e lança em falha de rede. Contratante (etapa 1), partes do contrato de consumo e endereço dos substabelecidos usam a mesma função; cada tela mantém a sua mensagem e o que faz com o resultado. O CEP é formatado por `formatCEP`, também de `endereco.ts`. O endereço só entra pelo CEP: rua, bairro, cidade e UF ficam travados e o usuário digita só CEP, número e complemento. Única exceção: CEP não encontrado ou ViaCEP fora mostra "Preencher o endereço à mão", que libera a digitação. Endereço salvo de contrato antigo aparece travado, com "Trocar endereço (informar CEP)". PJ continua preenchida pela Receita.
_Avoid_: fetch direto para viacep.com.br numa tela, formatador de CEP local
