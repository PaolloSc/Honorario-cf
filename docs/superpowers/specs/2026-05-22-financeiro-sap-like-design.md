# Financeiro SAP-like — Design Spec

**Data:** 2026-05-22
**Status:** aprovado para implementação
**Modelo de referência:** ContaAzul (Brazilian SaaS ERP), inspirado em SAP MM/FI

## Goal

Replicar lógica contábil da Planilha de Participações 2026 no módulo financeiro do Honorario-cf, padronizando vocabulário fiscal (SAP-like). Cobre 3 gaps restantes:

1. **Imposto agregado** (15.45% PIS+COFINS+IRRF+CSLL) — modelado como Tax Code editável
2. **Tipos de cobrança** (mensal, hora, avulso, êxito, pró-labore, partido) — enum
3. **Natureza expandida** (captação, performance, captação+performance, Projeto OpT) — enum
4. **Tipo de documento** (NF emitida, "emitir", "recebimento manual", recibo) — enum
5. **NF flexível** — já parcial via `nf_referencia`, expandido por `tipo_documento`

## Architecture

### Nova entidade `TaxCodeDB` (master data, editável)

```python
class TaxCodeDB(Base):
    __tablename__ = "tax_codes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(32), unique=True, nullable=False)          # 'PADRAO_1545'
    descricao = Column(String(256), nullable=False)
    aliquota_total = Column(Numeric(5, 4), nullable=False)            # 0.1545
    aliquota_iss = Column(Numeric(5, 4), nullable=False, default=0)
    aliquota_pis = Column(Numeric(5, 4), nullable=False, default=0)
    aliquota_cofins = Column(Numeric(5, 4), nullable=False, default=0)
    aliquota_irrf = Column(Numeric(5, 4), nullable=False, default=0)
    aliquota_csll = Column(Numeric(5, 4), nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=utcnow)
    criado_por = Column(String(256), nullable=False)
```

Seed inicial:
- `PADRAO_1545` — `aliquota_total=0.1545`, ISS=0, PIS=0.0065, COFINS=0.03, IRRF=0.015, CSLL=0.01

### Enums (Python constants — sem tabela)

```python
TIPOS_COBRANCA = ("mensal", "hora", "avulso", "exito", "prolabore", "partido")
NATUREZAS_PAGAMENTO = ("captacao", "performance", "captacao_performance", "projeto_opt")
TIPOS_DOCUMENTO = ("nf", "emitir", "recebimento_manual", "recibo")
```

### `ParticipacaoPagamentoDB` — colunas adicionadas

```python
tax_code_id = Column(Integer, ForeignKey("tax_codes.id"), nullable=False)
valor_bruto = Column(Numeric(12, 2), nullable=False)          # NOVO — antes só guardava liquido
imposto_total = Column(Numeric(12, 2), nullable=False, default=0)
tipo_cobranca = Column(String(32), nullable=True)             # enum TIPOS_COBRANCA — opcional, sobrescreve ParticipacaoDB.tipo_honorario por pagamento quando setado (caso de pagamentos mistos)
natureza_pagamento = Column(String(32), nullable=True)        # enum NATUREZAS_PAGAMENTO
tipo_documento = Column(String(32), nullable=False, default="nf")  # enum TIPOS_DOCUMENTO
```

Colunas preexistentes mantidas: `valor_liquido_recebido`, `valor_participacao`, `parcela_num`, `parcela_total`, `nf_referencia`, `status`, `dentro_limite_temporal`, `observacoes`.

## Data Flow — cálculo do pagamento

```
Input: valor_bruto, tax_code_id, percentual_captacao, percentual_performance, discriminado

1. tax_code = TaxCodeDB.get(tax_code_id) or default 'PADRAO_1545'
2. imposto_total = round(valor_bruto * tax_code.aliquota_total, 2)
3. valor_liquido = valor_bruto - imposto_total                          # G da planilha
4. valor_contratual = split_contratual_sucumbencial(valor_liquido, discriminado, body.valor_contratual)
   # reutiliza helper existente — se discriminado=False, aplica 50/50; se True, usa body.valor_contratual ou liquido inteiro
5. pct_efetivo = percentual_captacao + percentual_performance           # da ParticipacaoDB
6. valor_participacao = round(valor_contratual * pct_efetivo / 100, 2)  # H da planilha
```

Substitui cálculo atual onde `valor_liquido_recebido` era input direto. Agora `valor_bruto` é input, líquido é derivado.

## Components

### Backend — novos arquivos/changes

- **Migration `0005_tax_codes_sap_like.py`** — cria `tax_codes`, seed, adiciona 6 colunas, backfill
- **`app/models/tax_code.py`** — Pydantic schemas: `TaxCodeCreate`, `TaxCodeUpdate`, `TaxCodeOut`
- **`app/routers/tax_codes.py`** — CRUD endpoints (require_financeiro)
- **`app/services/participacao_calculator.py`** — refactor `calcular_valor_participacao` para usar `valor_bruto + tax_code`
- **`app/routers/participacoes.py`** — `RegistrarPagamentoRequest` ganha `valor_bruto`, `tax_code_id`, `tipo_cobranca`, `natureza_pagamento`, `tipo_documento`. `PagamentoResponse` expande retorno.
- **`app/main.py`** — wire router `tax_codes`

### Endpoints novos

```
GET    /api/tax-codes                                 -> lista (require_financeiro)
GET    /api/tax-codes/default                         -> retorna PADRAO_1545
POST   /api/tax-codes                                 -> cria (require_financeiro)
PATCH  /api/tax-codes/{id}                            -> atualiza (require_financeiro)
POST   /api/tax-codes/{id}/desativar                  -> ativo=False (require_financeiro)
```

### Frontend — novos arquivos/changes

- **`frontend/src/app/lib/finance-api.ts`** — cliente Tax Codes
- **`frontend/src/components/financeiro/AbaImpostos.tsx`** — tabela + form CRUD
- **`frontend/src/app/financeiro/page.tsx`** — adiciona tab `impostos` + atualiza `FormPagamento` com selects (tax_code, tipo_cobranca, natureza_pagamento, tipo_documento) + cálculo realtime
- **Tabela pagamentos** — colunas: Data | NF | Parcela | Tipo Doc | Tipo Cobr | Natureza | Bruto | Imposto | Líquido | Participação | Status | Obs (horizontal scroll OR linha expansível)

## Error Handling

| Cenário | Resposta |
|---|---|
| `tax_code_id` inexistente | 422 |
| `tax_code_id` inativo | 422 ("Tax code desativado, escolha outro") |
| `tipo_cobranca` fora de enum | 422 com lista aceitos |
| `natureza_pagamento` fora de enum | 422 |
| `tipo_documento` fora de enum | 422 |
| `valor_bruto <= 0` | 422 |
| `aliquota_total > 1` (>100%) | 422 ("Alíquota inválida") |
| Soma das alíquotas individuais ≠ aliquota_total | warning log, aceita (operador pode auditar) |
| Tentar desativar PADRAO_1545 (último ativo) | 422 ("Pelo menos um tax_code deve estar ativo") |

## Testing

| Arquivo | Cobertura |
|---|---|
| `tests/test_tax_codes.py` | CRUD endpoints, seed, validação alíquotas |
| `tests/test_pagamento_calculo.py` | Fórmula bruto→imposto→líquido→participação com PADRAO_1545 e ISENTO |
| `tests/test_pagamento_enums.py` | Validação `tipo_cobranca`, `natureza_pagamento`, `tipo_documento` |
| `tests/test_migration_backfill.py` | Verifica rows pré-migration têm `tax_code_id`, `valor_bruto` reverse-calc, `tipo_documento='nf'` |

Suite atual (60 passed) re-roda sem regressão.

## Migration

```python
# 0005_tax_codes_sap_like.py
def upgrade():
    # 1. cria tabela tax_codes + seed PADRAO_1545
    # 2. ALTER participacao_pagamentos ADD COLUMN x6
    # 3. backfill:
    #    - tax_code_id = id do PADRAO_1545
    #    - tipo_documento = 'nf'
    #    - valor_bruto = round(valor_liquido_recebido / (1 - 0.1545), 2)
    #    - imposto_total = valor_bruto - valor_liquido_recebido
    #    - tipo_cobranca = JOIN participacoes.tipo_honorario
    #    - natureza_pagamento = CASE captacao/performance/captacao_performance baseado em pcts
    # 4. CREATE INDEX idx_pagamento_natureza

def downgrade():
    # reverse all
```

## Authorization

| Action | Role |
|---|---|
| Listar/ler tax_codes | financeiro, admin |
| Criar/editar/desativar tax_codes | financeiro, admin (mudança de require_admin originalmente proposto) |
| Registrar pagamento com novos campos | financeiro, admin |

## Out of Scope

- Tabela auxiliar `iss_por_municipio` (futuro, se atender múltiplos municípios)
- Import CSV em massa (futuro)
- Integração API Receita Federal (não existe API pública, manual é viável)
- Tabela `internal_orders` / WBS Elements (Projeto OpT modelado como enum, não entidade)
- Auditoria fiscal completa (SPED, EFD-Reinf) — fora do MVP financeiro interno

## Decisions Log

| # | Decisão | Razão |
|---|---|---|
| 1 | Modelo híbrido ContaAzul (TaxCode tabela, resto enum) | Equilibra flex + simplicidade. Alíquota muda raramente mas precisa CRUD; enums estáveis. |
| 2 | `require_financeiro` em CRUD tax_codes (não `require_admin`) | Setor financeiro tem responsabilidade fiscal, evita gargalo no admin. |
| 3 | `valor_bruto` como input (vs líquido) | Replica planilha (coluna E = bruto, F = imposto, G = líquido). Permite recalcular se alíquota muda. |
| 4 | Backfill calcula `valor_bruto` reverso de líquido pré-existente | Rows antigas vieram sem tracking bruto; reverse calc com 15.45% é aproximação aceitável. |
| 5 | Manual sourcing (sem API Receita Federal) | Não existe API pública oficial. Alíquotas federais mudam raramente. ContaAzul também é manual. |
| 6 | Projeto OpT como enum (não entidade `internal_orders`) | YAGNI — basta categorizar, sem tracking por projeto separado. Pode evoluir se necessário. |
| 7 | `tipo_documento` enum vs string livre | Enum dá consistência (relatórios filtram por tipo). Texto livre fica em `nf_referencia`. |

## References

- Planilha de Participações 2026 (Copia) — análise da lógica original
- ContaAzul: master data tables (Impostos, Centros de Custo, Categorias) + enums fixos
- SAP MM/FI: Tax Code (`MWSKZ`), Document Type (`BLART`), Cost Center, Internal Order — patterns inspirados, não implementação literal
