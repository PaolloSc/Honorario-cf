# 03: Formato versionado dos Dados do contrato

**What to build:** o Estado do wizard grava um número de versão do formato; abrir converte qualquer formato anterior para o atual em um só lugar (a mesma função que o script do ticket 04 vai usar). O backend aceita e preserva esse número.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Snapshot novo traz o número de versão
- [ ] Formatos sem número abrem como a versão anterior
- [ ] Backend não rejeita nem descarta o campo
- [ ] Função de conversão pura, testada com os formatos antigos conhecidos
