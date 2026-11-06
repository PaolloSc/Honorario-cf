# 04: Script de conversão do banco (rascunhos e versões)

**What to build:** script que converte os Dados do contrato já salvos para o formato atual, com modo dry-run que mostra o que mudaria. Antes de rodar em produção: branch de backup no Neon, resultado do dry-run enviado ao responsável e **ok final explícito**. Nunca roda sem esse ok.

**Blocked by:** 03

**Status:** script pronto e dry-run feito em branch Neon descartável; EXECUÇÃO EM PRODUÇÃO pendente de backup + ok final do responsável

**Entregue:** `backend/scripts/converter_formato.py` (dry-run por padrão; `--apply` recusa sem `--backup` e `--ok`), `frontend/scripts/converter-formato.ts` (+ `.check.ts`) que reusa `normalizarFormData`. Trava: versão só é convertida se o DOCX regerado não mudar. Dry-run de 05/11/2026 na branch criada de produção: ver PR.

- [ ] Dry-run lista, por contrato/rascunho, o que mudaria, sem gravar
- [ ] Rodar duas vezes dá o mesmo resultado (idempotente)
- [ ] Teste com dados fictícios nos formatos antigos
- [ ] Backup criado e ok registrado antes de qualquer escrita em produção
