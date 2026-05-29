# Honorários, CEP e CNPJ — datas em calendário e revelação progressiva

**Data:** 2026-05-28
**Status:** Aprovado (design)

## Objetivo

Três melhorias de UX no wizard de contrato (`frontend/src/components/steps/`):

1. **Honorários:** campos de data devem ser apenas calendário (sem digitação manual, sem texto livre paralelo).
2. **CEP (PF):** campos de endereço ficam ocultos até o usuário preencher o CEP; depois aparecem, com o endereço auto-preenchido travado (read-only).
3. **CNPJ (PJ):** Razão Social e Endereço ficam ocultos até o lookup do CNPJ; depois aparecem travados (read-only).

## Escopo

- **Alterados:** `Step1Contratante.tsx`, `Step3Honorarios.tsx`, `backend/app/services/contract_generator.py`.
- **Não alterados:** `src/types/contract.ts`, `backend/app/models/contract.py` (campos `*_obs` continuam opcionais no modelo; apenas somem da UI).
- **Sem novas dependências.** `react-day-picker` e `date-fns` já instalados.
- A página de edição (`contracts/[id]/edit`) reaproveita os mesmos componentes → mudanças propagam automaticamente.

## Parte A — Honorários (Step3Honorarios.tsx)

### Estado atual
Datas já usam `DatePicker` / `DateRangePicker` (botão fechado → abre calendário → seleciona → fecha; sem digitação manual). Isso já satisfaz "fechado, só selecionar".

### Mudança
Remover os 4 inputs de **texto livre de "Observação" de vencimento**, mantendo apenas os calendários:

| Tipo        | Campo de texto removido       |
|-------------|-------------------------------|
| Pró-labore  | `vencimento_obs`              |
| Pró-labore  | `vencimento_parcelas_obs`     |
| Mensalidade | `dia_vencimento_obs`          |
| Êxito       | `vencimento_obs`              |

- Os `DatePicker` correspondentes permanecem.
- Os campos `*_obs` continuam existindo no tipo TS e no modelo backend (opcionais) — apenas deixam de ser editáveis na UI. Como ficam `undefined`, o backend emite só a data.
- `dia_vencimento` (texto legado) já não tem input na UI; permanece com o default `"5"` da inicialização. Sem mudança.

## Parte B — Backend: vencimento recorrente (contract_generator.py)

`_vencimento_combined(data, obs, legacy, *, recorrente=False)` hoje, quando `data` está presente, sempre formata `"em DD/MM/YYYY"`. Para vencimentos **recorrentes** (mensalidade, parcelas de pró-labore) sem o texto livre, isso fica errado.

### Mudança
Quando `recorrente=True` **e** `data` presente, usar o dia do calendário:

```
recorrente + data       →  "todo dia DD"
não-recorrente + data   →  "em DD/MM/YYYY"   (inalterado)
```

A concatenação de `(obs)` quando `obs` presente permanece (compatibilidade com contratos antigos que tenham obs salvo).

Afeta: mensalidade (`recorrente=True`), parcelas de pró-labore (`recorrente=True`). Êxito e pró-labore à vista permanecem `"em DD/MM/YYYY"`.

## Parte C — CEP (PFForm em Step1Contratante.tsx)

### Estado atual
CEP, Número, Complemento e "Endereço completo" sempre visíveis. Número/Complemento ficam `disabled` até `cepData`.

### Mudança — revelação progressiva + trava
- **Ocultar** Número, Complemento e Endereço completo enquanto `cepData == null`.
- Após lookup do CEP com sucesso (`cepData != null`):
  - Revelar Número e Complemento → **editáveis** (não vêm do CEP; usuário digita).
  - Revelar Endereço completo → **read-only** (montado automaticamente a partir de CEP + número + complemento).
- CEP, Nome, CPF, Nacionalidade, Profissão, Estado Civil, E-mail permanecem visíveis o tempo todo.

## Parte D — CNPJ (PJForm em Step1Contratante.tsx)

### Estado atual
CNPJ, E-mail, Razão Social, Endereço e checkbox de representante sempre visíveis. Só existe estado de loading/erro do lookup — não há flag de "sucesso".

### Mudança — revelação progressiva + trava
- Introduzir flag de **sucesso do lookup** (estado `cnpjLoaded` por índice, setado no sucesso do `handleCNPJLookup`).
- **Ocultar** Razão Social e Endereço enquanto o lookup não tiver sucesso.
- Após sucesso:
  - Revelar Razão Social → **read-only** (da Receita).
  - Revelar Endereço → **read-only** (da Receita).
- **Checkbox "Adicionar representante" permanece SEMPRE visível** (independe do CNPJ); o bloco do representante continua editável.
- CNPJ e E-mail permanecem visíveis o tempo todo.

## Tratamento de erros / casos de borda

- **ViaCEP/Receita com dado incompleto:** como os campos auto-preenchidos são read-only puro (sem botão "Editar" — decisão do usuário), dados incompletos não são corrigíveis diretamente nesse campo. No CEP, Número/Complemento (editáveis) compensam parcialmente. Risco aceito.
- **Erro no lookup:** mensagem de erro já existente é mantida; campos auto-preenchidos continuam ocultos (lookup não teve sucesso).
- **Edição de contrato existente** com endereço/razão já preenchidos: a revelação deve considerar dados já presentes como "carregados" para não esconder dados de contratos salvos. Tratar na inicialização do estado (se `endereco`/`razao_social` já vêm preenchidos, considerar revelado: `cnpjLoaded` inicia `true` se `razao_social` preenchida; CEP considera `cepData` derivável da `endereco` salva ou trata endereço salvo como revelado).

## Critérios de sucesso

1. Honorários: nenhum input de texto de "Observação" de vencimento; só calendários.
2. Contrato gerado de mensalidade recorrente diz "todo dia DD".
3. PF: endereço só aparece após CEP; "Endereço completo" não editável.
4. PJ: Razão Social/Endereço só aparecem após lookup do CNPJ e não editáveis; checkbox representante sempre visível.
5. Edição de contrato salvo continua mostrando dados já preenchidos.
6. `npm run build` (frontend) e testes do backend passam.
