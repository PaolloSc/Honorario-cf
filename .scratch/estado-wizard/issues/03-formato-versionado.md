# 03: Formato versionado dos Dados do contrato

**What to build:** o Estado do wizard grava um número de versão do formato; abrir converte qualquer formato anterior para o atual em um só lugar (a mesma função que o script do ticket 04 vai usar). O backend aceita e preserva esse número.

**Blocked by:** 01

**Status:** done

**Entregue:** `VERSAO_FORMATO = 2` e `versao_formato` nos Dados do contrato; `normalizarFormData` (pura, idempotente) é a conversão única que o ticket 04 reutiliza; sem número = formato 1. Backend: `ContratoRequest.versao_formato` (antes o /generate descartava o campo via model_dump), com teste.

- [ ] Snapshot novo traz o número de versão
- [ ] Formatos sem número abrem como a versão anterior
- [ ] Backend não rejeita nem descarta o campo
- [ ] Função de conversão pura, testada com os formatos antigos conhecidos
