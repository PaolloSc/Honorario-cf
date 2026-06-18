# Participação: base por Escopo ou Honorário

**Data:** 2026-05-29
**Status:** Aprovado (design)

## Problema

Hoje a etapa 5 (Participação — ficha interna) registra valor, para quem,
natureza, responsáveis e contato, mas não vincula a participação a um escopo ou
honorário específico do contrato. Falta registrar **sobre o que** incide a
participação.

## Objetivo

Adicionar uma escolha obrigatória, no início da participação, da **base**:
- **Escopo** — a participação incide sobre um escopo do contrato.
- **Honorário** — a participação incide sobre um honorário específico (que vive
  dentro de um escopo).

Depois de escolher a base e selecionar o item, o restante do fluxo segue
exatamente como hoje.

## Decisões (do brainstorming)

- **Seleção única** do item (radio), não múltipla.
- Para base = Honorário, listar **par escopo + honorário** (ex:
  "Consultoria LGPD — Mensalidade"), não apenas o tipo agregado.
- A base escolhida **aparece** na revisão (Step6) e no e-mail da ficha.
- O restante dos campos fica **travado** até um item de base ser selecionado.

## Modelo de dados

Novos campos opcionais em `Participacao` (frontend `types/contract.ts`,
backend `models/contract.py`, schema `routers/email.py`). Opcionais →
contratos legados continuam válidos.

```ts
base_tipo?: "escopo" | "honorario";
base_escopo_index?: number;      // índice do escopo na lista do contrato
base_honorario?: TipoHonorario;  // só quando base_tipo === "honorario"
base_label?: string;             // snapshot de texto p/ exibir e enviar
```

`base_label` é gerado no frontend no momento da seleção, para o backend
(e-mail/revisão) não precisar recomputar a partir dos escopos.

Formato do `base_label`:
- Escopo: `<label do escopo>` (ex: "Consultoria para implementação da LGPD")
- Honorário: `<label do escopo> · <label do honorário>`
  (ex: "Consultoria LGPD · Mensalidade")

## UI — Step5Participacao.tsx

Ordem dentro de `tem_participacao === true`:

1. **Radio "Base da participação"**: `Escopo` | `Honorário`
   (`base_tipo`). Trocar a base limpa `base_escopo_index`, `base_honorario`,
   `base_label`.
2. **Se Escopo** → lista radio (seleção única) dos escopos do contrato.
   Label via `ESCOPO_LABELS[escopo.tipo]` / `buildObjetoLines`. Seleção grava
   `base_escopo_index` e `base_label`.
3. **Se Honorário** → lista radio (única) de pares escopo+honorário, expandindo
   `escopos[i].honorarios[]`. Label `"<escopo> — <honorário>"`. Seleção grava
   `base_escopo_index`, `base_honorario`, `base_label`.
4. **Restante do bloco** (valor / para quem / natureza / responsáveis /
   contato) só renderiza quando há item de base selecionado
   (`base_label` preenchido).
5. **Sem escopos definidos** → mensagem "Defina escopos na etapa 2 primeiro";
   listas não aparecem.

### Labels de honorário

Hoje existe só um array local `TIPO_HONORARIOS` em `Step3Honorarios.tsx`
(não exportado). Adicionar um mapa compartilhado em `types/contract.ts`:

```ts
export const HONORARIO_LABELS: Record<TipoHonorario, string> = {
  hora_trabalhada: "Hora Trabalhada",
  pro_labore: "Pró-labore",
  mensalidade: "Mensalidade",
  exito: "Êxito",
  permuta: "Permuta",
};
```

Step3 pode (opcionalmente) reusar esse mapa; não é obrigatório nesta entrega.

## Exibição

### Step6Revisao.tsx
Adicionar, no topo da lista de participação, uma linha:
- `Base: Escopo — <base_label>` ou `Base: Honorário — <base_label>`.

### email.py (`/send-participacao`)
Adicionar campos ao schema e, em `rows`, uma linha no topo:
- `("Base", "Escopo — <base_label>")` ou `("Base", "Honorário — <base_label>")`,
  exibida só quando `base_tipo` e `base_label` presentes.

## Persistência / envio

- `Step7Envio` / `app/lib/api.ts`: incluir os 4 campos no payload de envio da
  ficha.
- Backend `models/contract.py` e `routers/email.py`: aceitar os 4 campos;
  normalização legado mantém todos opcionais (ausência = sem base, fluxo antigo).

## Fora de escopo

- Nenhum cálculo de valor muda; a base é registro/vínculo, não afeta valores.
- Step3 não é refatorado além de (opcional) reusar `HONORARIO_LABELS`.
- Migração de dados: não há; campos novos são opcionais.

## Testes

- **Backend**: `test_participacao_model.py` / `test_participacao_ficha.py` —
  campos novos aceitos; ausência mantém compat legado; e-mail inclui linha
  "Base" quando presente.
- **Frontend**: render Step5 — base obrigatória trava o restante; troca de base
  limpa seleção; sem escopos mostra aviso.
```
