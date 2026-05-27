# Design — Alterações Honorario-cf (Logo + Cláusulas + Wizard)

**Data:** 2026-05-26
**Origem:** `INSTRUÇOS.MD` (raiz Honorario-cf) + modelo padrão `2026 Contrato de Honorários Modelo Padrão.docx`

## Escopo

Quatro mudanças no app Honorario-cf:

1. Substituir logo SVG inline por PNG oficial (Drive) + garantir link header funcional
2. Corrigir texto/acentuação na tela de login
3. Adicionar cláusula opt-in "Partes Relacionadas" (2.4 + 2.4.1) ao gerador de contrato, com variante de solidariedade correspondente
4. Transformar campo "Natureza da participação" em `<select>`

Itens 1–4 são independentes. Item 3 é o único com impacto em backend + modelo de dados.

## Arquivos afetados

| # | Arquivo | Mudança |
|---|---------|---------|
| 1 | `frontend/public/brand/logo-horizontal-verde.png` | Novo (download Drive) |
| 1 | `frontend/public/brand/logo-horizontal-bege.png` | Novo (download Drive) |
| 1 | `frontend/src/components/ui/Logo.tsx` | Reescrever: `<img>` ao invés de SVG inline |
| 1 | `frontend/src/app/layout.tsx` | Garantir `<Link href="/">` Next.js no header |
| 2 | `frontend/src/app/login/page.tsx` | "Sistema de Honorarios" → "Contrato de Honorário"; "Faca" → "Faça"; "escritorio" → "escritório" |
| 2 | `frontend/src/app/financeiro/login/page.tsx` | Verificar mesmas correções se aplicável |
| 3 | `frontend/src/types/contract.ts` | Novo campo `incluir_partes_relacionadas?: boolean` em `ContratoRequest` |
| 3 | `frontend/src/components/steps/Step3Honorarios.tsx` | Checkbox condicional "Incluir cláusula Partes Relacionadas" |
| 3 | `frontend/src/components/steps/Step6Revisao.tsx` | Mostrar flag se ativa |
| 3 | `backend/app/models/contract.py` | Novo campo Pydantic `incluir_partes_relacionadas: bool = False` |
| 3 | `backend/app/services/contract_generator.py` | Inserir 2.4 + 2.4.1 em `_add_objeto_escopo`; variante COM/SEM Parte Relacionada em `_add_common_clauses` |
| 4 | `frontend/src/components/steps/Step5Participacao.tsx` | `<Input>` → `<select>` (5 opções) |

## Item 1 — Logo header

### Logos a baixar
- Drive folder `17L8boHXJlXNcboltW-rgONdZ_2O5ECKZ/35 anos/PNG/`:
  - `horizontal-verde.png` (id `120rJCOzfdg3dmxq2DDNOpw6doBWUpwRE`) → `logo-horizontal-verde.png`
  - `horizontal-bege.png` (id `10PNWdbfc-UqYlg6TCMpNgFdJMjoQSzrB`) → `logo-horizontal-bege.png`

Salvar em `frontend/public/brand/`.

### Logo.tsx
```tsx
interface LogoProps {
  variant?: "dark" | "light";
  className?: string;
  showSubtitle?: boolean;  // mantido pra compat, ignorado (PNG já tem subtítulo)
}

export default function Logo({ variant = "dark", className = "" }: LogoProps) {
  const src = variant === "dark"
    ? "/brand/logo-horizontal-verde.png"
    : "/brand/logo-horizontal-bege.png";
  return (
    <img
      src={src}
      alt="Carvalho & Furtado Advogados"
      className={className}
    />
  );
}
```

Usar `next/image` opcional (otimização) — manter `<img>` simples se não houver requisito de perf.

### Link header
`layout.tsx:36` — verificar wrapper. Se `<a href="/">` puro, trocar por `<Link href="/">` do `next/link`.

## Item 2 — Texto login

`frontend/src/app/login/page.tsx`:

| Linha | De | Para |
|-------|-----|------|
| 23 | `Sistema de Honorarios` | `Contrato de Honorário` |
| 26 | `Faca login` | `Faça login` |
| 26-27 | `escritorio` | `escritório` |

Aplicar correções equivalentes em `financeiro/login/page.tsx` se houver mesmos textos.

## Item 3 — Cláusula 2.4 Partes Relacionadas (OPT-IN)

### Modelo de ativação
Flag explícita no wizard. Cláusula gerada **apenas quando**:
```
data.incluir_partes_relacionadas == True
  AND (
    qualquer escopo tem TipoHonorario.HORA_TRABALHADA
    OR qualquer escopo tem TipoHonorario.MENSALIDADE com subtipo PROCESSO
  )
```

Se condição não atendida (flag false OU sem tipo aplicável) → omitir cláusula 2.4 + 2.4.1, e usar variante "SEM PARTE RELACIONADA" na seção 4.

### Frontend — `Step3Honorarios.tsx`
Adicionar checkbox no final do step, exibido apenas quando algum escopo já selecionado tem hora_trabalhada ou mensalidade_processo:

```tsx
{hasHoraOuMensalidadeProcesso && (
  <FormField label="">
    <label className="flex items-center gap-2">
      <input
        type="checkbox"
        checked={data.incluir_partes_relacionadas || false}
        onChange={(e) => onChange({
          ...data,
          incluir_partes_relacionadas: e.target.checked,
        })}
      />
      <span>Incluir cláusula de Partes Relacionadas (2.4)</span>
    </label>
  </FormField>
)}
```

### Backend — `models/contract.py`
```python
class ContratoRequest(BaseModel):
    # ... campos existentes
    incluir_partes_relacionadas: bool = False
```

### Backend — `contract_generator.py`

**`_add_objeto_escopo`** (após bloco condicional existente, antes de `_add_fee_details`):

```python
# Detecta elegibilidade
has_mensalidade_processo = any(
    TipoHonorario.MENSALIDADE in e.honorarios
    and e.mensalidade
    and e.mensalidade.subtipo in (SubtipoMensalidade.POR_PROCESSO, SubtipoMensalidade.POR_PASTA)
    for e in data.escopos
)

if data.incluir_partes_relacionadas and (has_hora or has_mensalidade_processo):
    doc.add_paragraph(
        f"2.{clause_num}. Para fins deste Contrato, são Partes Relacionadas: "
        "(i) cônjuge, companheiro(a) ou parente de primeiro ou segundo grau da "
        "CONTRATANTE; (ii) entidade(s) ou pessoa(s) jurídica(s) cujo controle "
        "fático ou jurídico seja da CONTRATANTE."
    )
    doc.add_paragraph(
        f"2.{clause_num}.1. Caso a CONTRATANTE solicite atendimento a Partes "
        "Relacionadas, salvo ajuste expresso em contrário, serão aplicados os "
        "mesmos critérios de honorários previstos no Contrato, constituindo "
        "nova contratação para todos os fins."
    )
    clause_num += 1
```

**`_add_common_clauses`** — anexar variante de solidariedade (atualmente ausente):

```python
if data.incluir_partes_relacionadas and (has_hora or has_mensalidade_processo):
    solidariedade = (
        "Caso qualificada mais de uma pessoa ou entidade no campo CONTRATANTE, "
        "haverá solidariedade entre elas, assim como no caso de prestação de "
        "serviço a Partes Relacionadas. Na hipótese de obrigações devidas ao "
        "C&F, as Partes reconhecem a possibilidade de encontro de contas, "
        "deduções e compensações ainda que multilaterais entre as partes "
        "signatárias e/ou Partes Relacionadas, de modo a adimplir tais "
        "obrigações em ordem preferencial."
    )
else:
    solidariedade = (
        "Caso qualificada mais de uma pessoa ou entidade no campo CONTRATANTE, "
        "haverá solidariedade entre elas. Na hipótese de obrigações devidas ao "
        "C&F, as Partes reconhecem a possibilidade de encontro de contas, "
        "deduções e compensações ainda que multilaterais entre as partes "
        "signatárias, de modo a adimplir tais obrigações em ordem preferencial."
    )
clauses.append(solidariedade)
```

Função `_add_common_clauses` precisa receber `data` (assinatura muda: `def _add_common_clauses(self, doc: Document, data: ContratoRequest)`). Atualizar caller.

## Item 4 — Natureza participação → `<select>`

`Step5Participacao.tsx:140-151`:

```tsx
<FormField label="Natureza da participação">
  <select
    value={participacao.natureza || ""}
    onChange={(e) => onChange({
      ...participacao,
      natureza: e.target.value,
    })}
    className="..."  // herdar classe Input existente
  >
    <option value="">Selecione a natureza da participação</option>
    <option value="Captação">Captação</option>
    <option value="Performance">Performance</option>
    <option value="Captação e performance">Captação e performance</option>
    <option value="Projeto">Projeto</option>
    <option value="Outro">Outro</option>
  </select>
</FormField>
```

Valores enviados ao backend mantêm string. Sem mudança de modelo.

## Testes / Verificação

- `npm run dev` → abrir `/login` → ver logo PNG + texto "Contrato de Honorário"
- Header em rota autenticada → clicar logo redireciona pra `/`
- Wizard: escopo com hora trabalhada → checkbox Partes Relacionadas aparece; sem ele, oculto
- Gerar contrato com flag ON → DOCX seção 2 tem 2.4 + 2.4.1; seção 4 tem variante "COM PARTE RELACIONADA"
- Gerar contrato com flag OFF (ou sem tipo aplicável) → DOCX omite 2.4; seção 4 usa "SEM PARTE RELACIONADA"
- Step5 → dropdown Natureza mostra 5 opções; selecionar grava no payload

## Fora de escopo

- Revisão geral de acentuação em outras telas além de login (item 4 INSTRUÇOES). Faremos só no que estamos tocando.
- Migração para `next/image` (otimização de logo) — manter `<img>` simples.
- Outras divergências do gerador atual vs modelo padrão (cláusulas de propriedade intelectual, rescisão, etc.) — não pedido.
