---
status: accepted
---

# Formato versionado, conversão do banco por script e retomada na etapa exata

Os **Dados do contrato** já salvos (rascunhos e **Versões**) têm formatos antigos que o front converte ao abrir (vigência no pró-labore, parcelamento antigo). Decidimos gravar um número de versão do formato daqui para frente e converter o que já existe no banco de produção por script, para ter um formato único.

- O script só roda em produção depois de: branch de backup no Neon, **dry-run** com o resultado mostrado, e **ok final explícito** do responsável. Nunca roda sem esse ok.
- **Retomar** reabre o **Rascunho** na etapa exata, até a 7. Por isso a **Revisão por IA** e a **Prévia** precisam ser marcadas como **Revisão desatualizada** (e refeitas) quando os **Dados do contrato** mudaram desde a última revisão; antes só se voltava até a etapa 5 e a 6 e a 7 eram refeitas sempre.
- Alternativa rejeitada: continuar convertendo só ao abrir, sem tocar o banco (mais seguro, mas mantém dois formatos para sempre).
- Alternativa rejeitada: manter o limite da etapa 5 ao retomar (evita texto desatualizado, mas obriga a refazer a revisão toda vez).

## Consequências (ticket 04 e 07)

- A conversão ao abrir (`normalizarFormData`) **fica para sempre**: o script do banco não converte as versões cujo .docx regerado mudaria (vigência ainda no pró-labore), então elas dependem dela.
- `normalizarFormData` preserva campos que o wizard não conhece (topo, acessórios, ficha): campo novo no contrato = declarar o tipo em `types/contract.ts`; não há lista a atualizar em outro lugar.
