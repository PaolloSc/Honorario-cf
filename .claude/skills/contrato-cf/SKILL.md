---
name: contrato-cf
description: >
  Como mexer no contrato de honorários gerado pelo sistema do C&F Advogados —
  texto de cláusula, numeração, seções, qualificação das partes, campos do
  wizard e assinatura no DocuSeal. Use sempre que o pedido tocar no conteúdo
  ou na estrutura do contrato: feedback de advogado sobre o contrato gerado
  ("o contrato saiu com...", "a cláusula X deveria...", "mudar o título da
  seção", "tirar/incluir a cláusula Y", "a numeração está errada"), ajuste de
  redação jurídica, cláusula que só deve aparecer em certos casos, novo tipo
  de escopo ou honorário, ou qualquer mudança em contract_generator.py,
  models/contract.py e nas etapas Step1–Step7 do wizard. Vale também quando o
  pedido chega como print, e-mail ou lista de observações da equipe, sem citar
  arquivo nenhum.
---

# Contrato de honorários — C&F

O sistema é um wizard de 7 etapas que gera um `.docx` de contrato de
honorários, manda por e-mail para conferência e depois para assinatura no
DocuSeal. Quem usa são advogados do escritório; o feedback quase sempre chega
como uma lista de observações em português sobre o documento gerado — não como
issue técnica. Seu trabalho é traduzir cada observação para a camada certa.

## A regra que quebra tudo em silêncio

**Nunca escreva o número da cláusula no texto.** A numeração vem de uma lista
multinível do Word (`_ensure_clause_numbering`), para que apagar uma cláusula
no Word renumere as seguintes sozinho — foi um pedido explícito do escritório.

```python
self._add_secao(doc, "CLÁUSULAS GERAIS")        # nível 0 -> "4."
self._add_clausula(doc, "Todos os valores...")   # nível 1 -> "4.1."
self._add_clausula(doc, "Este prazo...", ilvl=2) # nível 2 -> "4.1.1."
```

Escrever `doc.add_paragraph("4.10. Nova cláusula")` não gera erro, passa
despercebido no texto do `.docx`, e só aparece no Word como cláusula fora da
sequência. `test_clausulas_sao_numeradas_pelo_word_e_nao_no_texto` existe
justamente para pegar isso — se ele quebrar, é porque alguém numerou à mão.

Consequência prática: **ler `word/document.xml` mostra as cláusulas sem
número**. Para ver o contrato como o advogado o lê, use o script abaixo.

## Sempre comece gerando e olhando

```bash
cd backend
uv run python ../.claude/skills/contrato-cf/scripts/dump_contrato.py            # lista presets
uv run python ../.claude/skills/contrato-cf/scripts/dump_contrato.py pj-multi
uv run python ../.claude/skills/contrato-cf/scripts/dump_contrato.py pj-multi --docx /tmp/c.docx
```

Ele passa pelo mesmo conversor do preview da tela (`_docx_to_html`), que
recalcula a numeração a partir do nível da lista. Os presets cobrem as formas
que mais quebram: honorário único x vários, com e sem êxito, PJ com dois
representantes, cláusulas adicionais empurrando o Foro. Rode o preset afetado
antes e depois da mudança e compare — é mais rápido e mais confiável do que
raciocinar sobre o código.

Se o advogado mandou um caso real, salve o payload do wizard num `.json` e
passe o caminho no lugar do preset.

## Onde fica cada seção

Tudo em `backend/app/services/contract_generator.py`, montado na ordem de
`_build_document`. Os números abaixo são os que saem hoje; eles se deslocam
sozinhos se uma seção for inserida ou omitida.

| Seção | Método | Observação |
|---|---|---|
| 1. Das Partes | `_add_parties` | qualificação de PF/PJ, representantes legais |
| 2. Objeto, Escopo e Honorário | `_add_scope_and_fees` | tabela Escopo/Preço + cláusulas condicionais |
| 3. Outras Disposições sobre Honorários | `_add_fee_details` | despacha para os blocos por tipo de honorário |
| — Hora Trabalhada | `_add_hora_trabalhada` | |
| — Pró-labore | `_add_pro_labore` | |
| — Mensalidade | `_add_mensalidade` | 3 subtipos (partido / processo / pasta) |
| — Êxito | `_add_exito` | |
| — Permuta | `_add_permuta` | |
| 4. Cláusulas Gerais | `_add_common_clauses` | lista `clauses`, ordem = numeração |
| 5. Reembolsos, Despesas e Outras Verbas | `_add_accessories` | |
| 6. Obrigações das Partes | `_add_obligations` | |
| 7. Compliance | `_add_integrity` | |
| 8. Prazo, Rescisão e Outros Efeitos | `_add_term_and_termination` | |
| 9. Propriedade Intelectual | `_add_ip` | |
| 10. Disposições Gerais | `_add_general` | lista `gerais` |
| 11. Disposições Adicionais | `_add_general` | só existe se o advogado escreveu cláusulas livres |
| Foro (11 ou 12) | `_add_general` | número acompanha a seção anterior |

Para **mudar a redação de uma cláusula**, edite a string no método
correspondente. Para **mudar o título de uma seção**, edite o argumento de
`_add_secao` — sem o número, ele é gerado.

## O que é condicional

Isto é regra de negócio: não "simplifique" removendo a condição.

- **Bloco de honorário** só entra se o escopo tiver o objeto preenchido
  (`escopo.exito`, `escopo.hora_trabalhada`, ...).
- **Subtítulo do bloco** ("HORA TRABALHADA", "ÊXITO") e **subcláusulas** só
  existem com mais de um honorário. Com um só: numeração corrida (3.1, 3.2) e
  sem subtítulo. Controlado por `varios` em `_add_fee_details`.
- **5.6** (sucumbência / renúncia) só com honorário de êxito — `has_exito`.
- **8.3 tabela de fases processuais** só com êxito **e** sem
  `criterio_extincao_exito` preenchido. Com o critério, sai um texto livre
  ("quando da formalização do acordo") e a tabela some — é o caso de
  negociação extrajudicial, onde não existe fase processual.
- **8.4** (inocorrência de fase) acompanha a tabela.
- **2.3** muda conforme haja hora trabalhada; **2.4/2.4.1** dependem de
  `incluir_partes_relacionadas`; **2.x** de advocacia de partido só nesse
  subtipo.
- **Partes Relacionadas** na cláusula de solidariedade (seção 4) tem duas
  redações conforme `com_parte_relacionada`.

## Wizard: onde mora cada campo

`frontend/src/components/steps/` — cada etapa mapeia para um pedaço de
`ContratoRequest` (`backend/app/models/contract.py`). Tipos espelhados em
`frontend/src/types/contract.ts`: **mudança de modelo quase sempre exige tocar
nos dois**.

| Etapa | Arquivo | Modelo |
|---|---|---|
| 1 Contratante | `Step1Contratante.tsx` | `ContratantePF` / `ContratantePJ` / `RepresentantePJ` |
| 2 Escopo | `Step2Escopo.tsx` | `EscopoItem`, `TipoEscopo`, `ESCOPO_LABELS` |
| 3 Honorários | `Step3Honorarios.tsx` | `HoraTrabalhada`, `ProLabore`, `Mensalidade`, `Exito`, `Permuta` |
| 4 Acessórios | `Step4Acessorios.tsx` | `Acessorios` (inclui `valor_km`, `criterio_extincao_exito`, `clausulas_adicionais`) |
| 5 Participações | `Step5Participacao.tsx` | `Participacao` — **ficha interna, não vai para o contrato** |
| 6 Revisão | `Step6Revisao.tsx` | — |
| 7 Envio | `Step7Envio.tsx` | monta signatários, testemunhas, e-mail |

Novo tipo de escopo = enum + label em **`models/contract.py` e
`types/contract.ts`**. A ordem das chaves em `ESCOPO_LABELS` (frontend) define
a ordem no formulário — se pedirem "inserir como opção 2", é ali.

Campos antigos de contratos já salvos não podem sumir: `ContratantePJ` e
`Participacao` migram formatos legados num `@model_validator(mode="before")`.
Siga esse padrão ao trocar um campo por uma lista.

## Assinatura (DocuSeal)

`backend/app/routers/docuseal.py`, endpoint `send-for-signature`.

- Assinam pelo escritório: **C&F como `Contratado`** (injetado sempre) mais os
  advogados escolhidos na etapa 7. Quem preenche o formulário **não** é
  incluído automaticamente — foi removido de propósito, não reintroduza.
- **Testemunha 1** (financeiro) é injetada em toda submissão e recebe por
  último (`order = 5`), depois que todos assinaram.
- Papéis repetidos ganham sufixo ("Contratante 1", "Contratante 2") porque o
  DocuSeal exige papel único por signatário, e cada papel precisa casar com um
  campo de assinatura no `.docx` — por isso o documento é **regerado** com
  `signatario_roles` antes do envio.
- PJ com vários representantes legais gera **um signatário por representante**
  (empresas cuja assinatura só vale com dois administradores).
- As tags `{{Assinatura ...;type=signature;role=...}}` ficam **em texto
  branco**: invisíveis no Word, legíveis para o DocuSeal. Se mexer em
  `_format_paragraph`, preserve o ramo `is_tag` — senão a tag reaparece no
  documento do cliente.

Contrato que "não apareceu no DocuSeal" costuma ser configuração, não código:
`DOCUSEAL_BASE_URL` / `DOCUSEAL_API_KEY` apontam para a instância onde o
documento foi criado. Veja `docs/runbooks/docuseal-producao.md`.

## Preview

`_docx_to_html` em `backend/app/routers/contract.py` alimenta a prévia da tela
e o script acima. Ele **recalcula os números** a partir de `w:numPr/w:ilvl`,
porque no `.docx` eles não são texto. Ao mexer na numeração, ajuste os dois
lados ou a prévia passa a divergir do Word.

Duas armadilhas já custaram bug aqui:

- `cell.text` (python-docx) junta **todos os parágrafos da célula** num texto
  só, e o HTML colapsa a quebra de linha em espaço. Numa célula de assinatura
  isso cola o rótulo nos underscores. Renderize parágrafo a parágrafo com
  `<br>`.
- A prévia limpa as tags do DocuSeal (`_clean_preview_text`). Se o documento
  também desenha a linha de assinatura, trocar a tag por underscores duplica a
  linha — só um dos dois pode desenhá-la.

## Os mesmos dados, renderizados em vários lugares

Contrato, ficha de participação e e-mails renderizam o mesmo `ContratoRequest`
em telas diferentes. Toda vez que um campo mudou, as cópias saíram do ar em
momentos diferentes — foi assim que a ficha do DocuSeal ficou meses mostrando
menos informação que a do e-mail. Ao mexer num campo, **procure todos os
pontos que o exibem** antes de dar por encerrado:

| Onde | Arquivo |
|---|---|
| Revisão na tela (etapa 6) | `frontend/src/components/steps/Step6Revisao.tsx` |
| E-mail da ficha ao financeiro (no envio) | `backend/app/routers/email.py` |
| E-mail da ficha após todos assinarem | `backend/app/routers/docuseal.py` |
| Rascunho no financeiro | `backend/app/routers/contract.py` |
| Formatação compartilhada da ficha | `backend/app/utils/participacao.py` |

Dois modos de falha se repetem, e nenhum quebra teste nem levanta exceção —
só aparece como texto estranho no print que o advogado manda:

- **Coleção renderizada direto.** `{lista}` no JSX concatena sem separador
  ("AnaBruno"); em f-string Python vira `['Ana', 'Bruno']`. Sempre `join`.
- **Campo legado x estruturado.** Vários campos ganharam versão estruturada e
  o antigo virou fallback: `valor_tipo` + `valor_percentual`/`valor_monetario`/
  `valor_outro` sobre `percentual_ou_valor`; `representantes` sobre
  `representante_*`; `para_quem` lista sobre string. Ler só o campo antigo
  deixa a tela **vazia** para tudo que foi preenchido no wizard atual — que é
  o caso normal. Confira qual o wizard grava hoje (`Step*.tsx`), não qual o
  modelo ainda aceita.

## Verificação

```bash
cd backend && uv run pytest tests -q
```

`tests/test_contract_generator_fidelidade.py` é o guarda do texto: cada
cláusula que a equipe revisou tem uma asserção. Ao mudar redação a pedido do
escritório, **atualize a asserção junto** — o teste falhando é o sinal de que
a mudança pegou, não de que está errada. Testes que dependem do número
renderizado devem usar o helper `_preview_paras` (que passa pelo preview), não
`_paras_for` (texto cru, sem número).

### Veja o teste falhar

Aqui o bug chega como print de um advogado, então o teste quase sempre nasce
**depois** da correção — e um teste escrito assim tende a confirmar o presente
em vez de pegar o defeito. Vale reintroduzir o bug e conferir que ele fica
vermelho:

```bash
python3 .claude/skills/contrato-cf/scripts/verifica_vermelho.py
```

O script guarda, para cada bug já corrigido, o trecho certo, o trecho com o
defeito e o teste que deveria acusar. Na primeira execução, **2 dos 8 testes
passaram com o bug de volta** — um olhava só os parágrafos já dentro da lista
de numeração (uma cláusula numerada à mão fica fora dela, justamente o caso
que ele deveria pegar) e o outro casava um trecho que continuava batendo com a
linha duplicada presente. Ao corrigir um bug novo, acrescente a mutação.

O CI (`.github/workflows/ci.yml`) roda pytest, `tsc --noEmit` e `npm run
build`. Rode ao menos o pytest e o `tsc` antes de commitar.

Não dá para renderizar o `.docx` neste ambiente (o LibreOffice do container
está quebrado, falha até em arquivo trivial). Paginação, quebra de tabela
entre páginas e aparência da lista só o usuário confirma abrindo no Word —
gere o arquivo, entregue e peça a conferência em vez de afirmar que está certo.

## Ao responder feedback do escritório

Vale separar o que é código do que não é, porque parte das observações não se
resolve com diff:

- **Redação / cláusula condicional / título** → código, nos métodos acima.
- **Valor que virou campo** (custo do km, critério de extinção) → já existe em
  `Acessorios`; confira se o pedido é mudar o *padrão* ou preencher o campo.
- **Nome de pessoa faltando numa lista** (participações, testemunhas) → é
  cadastro (`colaboradores` / `testemunhas`), não código.
- **"Não apareceu no DocuSeal"** → configuração de ambiente.
- **Estética de paginação** → não verificável aqui; peça print.

Quando uma observação for ambígua a ponto de mudar o resultado (ex.: "o 3.5
podia se mesclar com o 3.6" — mesclar ou só reordenar?), implemente o resto e
pergunte só o item ambíguo, em vez de travar a leva inteira.
