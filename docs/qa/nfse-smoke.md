# Smoke E2E — NFS-e BH

Executar antes de habilitar `NFSE_ENABLED=true` em produção.

## Pré-requisitos

- Migrations 0001 e 0002 aplicadas.
- `NFSE_KEK`, `NFSE_WORKER_TOKEN`, `HONORARIO_API_URL` configurados.
- GH Actions secrets `HONORARIO_API_URL`, `NFSE_WORKER_TOKEN` + var `PRESTADORES_CNPJS` definidos.
- Credencial homolog PBH em mãos (ou produção se já em piloto).

## Roteiro

1. **Cadastrar credencial**
   - Login no honorario-cf como `admin`.
   - Acessar `/admin/credenciais-pbh`.
   - Preencher CNPJ + login + senha → "Salvar credencial".
   - Esperado: linha aparece em "Credenciais ativas" como **ativo**.

2. **Disparar sync via GH Actions**
   - GitHub → Actions → `nfse-sync` → "Run workflow".
   - Preencher `periodo_inicio` / `periodo_fim` se desejar.
   - Esperado: job verde com logs `ingest ok: ...`.

3. **Conferir lista de NFs no frontend**
   - `/financeiro` → aba "Notas Fiscais" → competência do mês de teste.
   - Esperado: ≥1 NF listada com status válido.

4. **Vinculação automática**
   - Ao menos 1 NF deve aparecer com badge **✓ auto** e `Contrato#...` populado.
   - Conferir na aba "Participações" do mesmo contrato: novo pagamento listado com valor líquido correto.

5. **Vinculação manual**
   - Encontrar NF com status **⚠ pendente** ou **✗ sem match**.
   - Clicar "Vincular" → digitar contract_id válido → "Confirmar".
   - Esperado: badge muda para **✓ manual**, pagamento aparece em Participações.

6. **Cancelamento**
   - Cancelar uma NF no portal BHISS (homolog).
   - Aguardar próximo sync OU disparar manual.
   - Esperado: NF na lista muda para **🚫 cancelada**; pagamento original PERMANECE (não revertido); alerta no banner.

7. **Credencial inválida**
   - Em `/admin/credenciais-pbh`, alterar a senha p/ valor errado.
   - Disparar sync manual.
   - Esperado: workflow conclui (não falha vermelho); credencial fica **inativo** com motivo `login_invalido`; banner vermelho aparece em /financeiro.

8. **Audit log**
   - Conferir tabela `nfse_audit_log` no DB. Esperado: entradas para `credencial.upsert`, `nfse.vincular_manual`, `sync.start`/`sync.end`.

## Critérios de aceite

- [ ] Itens 1-8 completados sem erro inesperado.
- [ ] Suíte unit verde.
- [ ] Suíte integration verde contra homolog.
- [ ] Pelo menos 1 NF auto-vinculada gerou pagamento na Participação com o valor correto.
- [ ] KEK rotation runbook executado em dev sem perda de credenciais.
