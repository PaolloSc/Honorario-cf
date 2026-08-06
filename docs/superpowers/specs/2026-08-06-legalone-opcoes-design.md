# Campos Legal One na ficha do financeiro

Data: 2026-08-06

## Problema

A Etapa 5 do wizard de Contrato de Honorários ("Participações — Ficha Interna") é o
bloco de informações repassadas ao financeiro por e-mail. Faltam três dados de
cadastro que o financeiro precisa lançar no Legal One:

- **Categoria do cliente** — valor único
- **Etiqueta LO** — múltiplos valores
- **Lista de transmissão** — múltiplos valores

As opções de cada campo vêm de tabelas do Legal One, que mudam com o tempo. Deixá-las
fixas no código obrigaria um deploy a cada alteração.

## Decisões

| Questão | Decisão |
|---|---|
| Origem das opções | Cadastráveis pelo admin, persistidas no banco |
| Posição no wizard | Etapa 5, em bloco próprio, **fora** do toggle "Este contrato terá participação?" |
| Cardinalidade | Categoria = 1 valor; Etiqueta e Lista = vários |
| Obrigatoriedade | Todos opcionais |
| Envio ao financeiro | A ficha passa a ser enviada quando há participação **ou** quando algum dos três campos foi preenchido |
| Valores iniciais | Listas começam vazias; o admin cadastra |

## Modelo de dados

Tabela única `legalone_opcoes` (migração `0008_legalone_opcoes`) — as três listas têm
forma idêntica, então três tabelas seriam o mesmo CRUD triplicado.

| coluna | tipo | nota |
|---|---|---|
| `id` | Integer PK | |
| `tipo` | String(32) | `categoria_cliente` \| `etiqueta` \| `lista_transmissao` |
| `valor` | String(256) | texto exibido no dropdown |
| `ativo` | Boolean, default true | desativado some do wizard, preserva histórico |
| `created_at` | DateTime | |

`UniqueConstraint(tipo, valor)` impede duplicata pelo banco, sem checagem no router.
Ordenação alfabética por `valor`.

Deliberadamente fora: `ordem` (alfabética resolve), `created_by`/`updated_at`
(ninguém consome), índice em `(tipo, ativo)` (a tabela terá dezenas de linhas).

## API

`backend/app/routers/legalone_opcoes.py`, espelhando `colaboradores.py`:

- `GET /api/legalone-opcoes` — autenticado. Devolve as três listas numa resposta só
  (`{categoria_cliente: [...], etiqueta: [...], lista_transmissao: [...]}`), evitando
  três chamadas do wizard. Aceita `?incluir_inativos=true`, este restrito a admin — é o
  403 desse parâmetro que faz a tela de manutenção exibir "Acesso Restrito".
- `POST /api/legalone-opcoes` — `require_admin`. Cria uma opção.
- `PATCH /api/legalone-opcoes/{id}` — `require_admin`. Liga/desliga `ativo`.

Sem `DELETE`: apagar exigiria varrer o JSON de todos os contratos para saber se a
opção está em uso. Desativar já a remove do wizard e preserva contratos antigos.

## Modelo do contrato

Três campos novos em `Participacao` (`backend/app/models/contract.py` e
`frontend/src/types/contract.ts`):

```
categoria_cliente: Optional[str]
etiquetas: list[str]
listas_transmissao: list[str]
```

As listas seguem o padrão de `para_quem`: o `model_validator` já existente coage
`None` → `[]` e `str` → `[str]`, garantindo compatibilidade com contratos salvos antes
desta mudança.

Limites de payload: `valor` até 256 caracteres (igual à coluna — sem isso o Postgres
devolve 500 onde o SQLite dos testes aceita), e na ficha cada item das listas até 256
caracteres, no máximo 50 itens por lista.

## Frontend

**Etapa 5** (`Step5Participacao.tsx`): bloco "Cadastro no Legal One" antes do toggle de
participação, sempre visível. `Select` para categoria, `Checkbox` (ambos já em
`components/ui/FormField.tsx`) para etiquetas e listas. Um valor salvo que não está mais
na lista ativa continua aparecendo — mesmo tratamento que `optionsComSalvo` dá aos
colaboradores removidos.

**Etapa 6** (`Step6Revisao.tsx`): bloco "Cadastro no Legal One" na revisão, exibido
quando algum dos três campos tem valor — inclusive em contrato sem participação.

**Etapa 7** (`Step7Envio.tsx`): a condição de envio da ficha passa de
`tem_participacao` para `tem_participacao || algum dos três campos preenchido`. O
payload é montado por `buildFichaPayload`, compartilhado pelos fluxos de criação e
edição, que só inclui os campos de participação quando o toggle está ligado — desligar
o toggle não limpa o que já foi digitado, e enviá-los assim faria o financeiro receber
uma participação que o contrato não tem.

**`ContractWizard.tsx`**: `normalizeFormData` reconstrói `participacao` por whitelist,
então os três campos precisam ser listados lá, sob pena de sumirem ao reabrir o
contrato para edição. Na mesma passagem foram incluídos os `base_*`, que já eram
descartados antes desta mudança pelo mesmo motivo.

**Admin** (`/admin/legalone`): página única com as três listas, cada uma com campo de
adicionar e toggle ativo/inativo por linha. Link no `UserMenu`.

## E-mail ao financeiro

Todo valor do payload passa por `html.escape` na montagem da tabela — o endpoint aceita
string arbitrária de qualquer usuário autenticado e não confere os valores contra
`legalone_opcoes`, então sem escape dava para embutir instrução falsa no e-mail que o
financeiro recebe com o DOCX anexado. A quebra de linha vira `<br>` **depois** do
escape, para o objeto do contrato continuar legível.

`send_participacao_email` ganha três linhas na tabela HTML (Categoria do cliente,
Etiqueta LO, Lista de transmissão — listas juntadas por vírgula), exibidas apenas
quando preenchidas. Quando não há participação, o assunto vira
"Cadastro Legal One — {cliente}" e as linhas de participação simplesmente não são
emitidas, porque cada linha já é condicional hoje.

## Testes

- `test_legalone_opcoes.py` — CRUD, unicidade `(tipo, valor)`, `tipo` inválido
  rejeitado, `POST`/`PATCH` negados a não-admin, `ativo=false` sumindo do `GET` padrão.
- `test_participacao_model.py` — os três campos aceitam ausência, `None` e string
  legada sem quebrar contratos antigos.
- `test_participacao_ficha.py` — as três linhas aparecem no HTML quando preenchidas e
  somem quando não; ficha enviada sem participação quando só os campos LO estão
  preenchidos.
