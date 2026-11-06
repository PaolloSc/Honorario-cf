# 04: Script de conversão do banco (rascunhos e versões)

**What to build:** script que converte os Dados do contrato já salvos para o formato atual, com modo dry-run que mostra o que mudaria. Antes de rodar em produção: branch de backup no Neon, resultado do dry-run enviado ao responsável e **ok final explícito**. Nunca roda sem esse ok.

**Blocked by:** 03

**Status:** ready-for-agent (execução em produção: só com ok do responsável)

- [ ] Dry-run lista, por contrato/rascunho, o que mudaria, sem gravar
- [ ] Rodar duas vezes dá o mesmo resultado (idempotente)
- [ ] Teste com dados fictícios nos formatos antigos
- [ ] Backup criado e ok registrado antes de qualquer escrita em produção
