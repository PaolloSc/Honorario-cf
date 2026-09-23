---
name: testar-regra
description: >
  Responde "e se a pessoa fizer X?" sobre uma regra de negócio do sistema de honorários do C&F:
  traça o caminho real pelo código (wizard → validação → backend → documento, ficha, e-mail,
  DocuSeal, financeiro), diz o que acontece hoje com evidência, acha os buracos e trava cada
  cenário num teste que fica vermelho antes da correção. Use sempre que a pergunta for sobre o
  comportamento de uma regra, mesmo sem a palavra "teste": "e se ela não preencher o percentual?",
  "o que o código faz quando...", "quem assina se o sócio for de outra área?", "e se escolher a
  Mônica como gestão e o Gabriel na participação?", "isso pode dar confusão?", "tem como passar
  sem X?", ou ao revisar se uma regra nova ficou fechada. Não use para mudar texto de cláusula
  (isso é a skill contrato-cf) nem para bug de tela quebrada.
---

# Testar regra — "e se a pessoa fizer X?"

Quem pergunta é advogado ou dono do sistema, não programador. A pergunta chega como um caso
("a Gabriela faz o contrato e marca a Mônica sem percentual") e quer saber o que o sistema faz
**de verdade** — não o que deveria fazer. A resposta vale pela evidência: cada afirmação aponta
para `arquivo:linha` ou para um teste que roda.

O valor desta skill está em achar o que ninguém perguntou: a pergunta é a porta de entrada,
mas os buracos costumam estar um passo ao lado (o dado aceito sem aviso que depois some da ficha;
a regra que só existe na tela; o fallback que ninguém vê).

## Fluxo

### 1. Transforme a pergunta em cenários concretos

Escreva o caso com nomes e valores reais do escritório (Mônica, Gabriel, Caio; 20%; Cível) e
derive as variações vizinhas antes de ler código — elas são onde os buracos moram:

- o campo vazio, o campo com valor, o campo com valor de outro tipo (R$ em vez de %);
- a pessoa que existe no cadastro, a que não existe, a inativa, a que mudou de papel;
- o contrato novo e o contrato **antigo** salvo antes da regra (campos legados, sem área);
- dois campos que parecem ligados mas não são (área × gestão × participação × quem assina);
- a regra na tela **e** a mesma chamada direto na API.

Liste de 3 a 8 cenários. Mais que isso vira ruído.

### 2. Trace o caminho real, camada por camada

Leia o código do `master` atualizado (`git fetch` e leia de `origin/master` ou de uma worktree
dele — o checkout local costuma estar numa branch atrasada). Para cada cenário, siga o dado:

| Camada | Onde fica | O que procurar |
|---|---|---|
| Tela e validação | `frontend/src/components/ContractWizard.tsx` (`validateStep`), `steps/Step*.tsx` | a regra existe? bloqueia ou só avisa? |
| Tipos | `frontend/src/types/contract.ts` ↔ `backend/app/models/contract.py` | campo existe dos dois lados? legado migrado no `model_validator`? |
| Backend | `backend/app/routers/*.py` | a API aceita o que a tela barra? |
| Contrato (.docx) | `services/contract_generator.py` | o dado entra no documento? |
| Ficha ao financeiro | `utils/participacao.py` → usada em `routers/email.py`, `routers/docuseal.py`, `routers/contract.py` (rascunho `ParticipacaoDB`) | as 3 cópias mostram o mesmo? |
| Revisão (passo 6) | `steps/Step6Revisao.tsx` | mostra igual à ficha? |
| Assinatura | `routers/docuseal.py` (`_resolver_assinatura_escritorio`, `socio_sugerido`) | quem recebe convite, em que ordem |
| Cadastro | tabela `colaboradores` (papel, ativo, `areas`) | casamento por nome ou e-mail? |

Termos do domínio (sócio, advogado, área, assinatura pelo escritório) estão em `CONTEXT.md`.

Quando a resposta depender de dado real ("o Marcelo Leite é sócio?"), consulte o banco **só
leitura**: `npx neonctl connection-string main --project-id curly-dawn-25704162 --pooled` e uma
consulta `SELECT`. Nunca altere dado de produção nesta skill.

### 3. Procure os buracos de sempre

Cada um destes já apareceu neste sistema. Passe por todos, mesmo os que parecem fora da
pergunta:

1. **Aceito sem validação** — marcou a Mônica sem valor e nada avisou.
2. **Salvo e descartado** — o wizard grava R$ por advogado, a ficha só lia o percentual; o valor
   sumia sem erro.
3. **Cópias divergentes** — a mesma informação renderizada em lugares diferentes (ficha em 3
   rotas, revisão no frontend) com regras diferentes.
4. **Fallback silencioso** — sem sócio, a assinatura ia para o e-mail genérico `contrato@` e
   ninguém via.
5. **Acoplamento sem querer** — o primeiro advogado da lista virava quem assina pelo escritório.
6. **Obrigatório que força dado errado** — área obrigatória sem opção para "área sem sócio"
   obriga a pessoa a mentir.
7. **Casamento frágil** — busca por nome exato (acento, espaço, "Marcelo" × "Marcello") em vez
   de e-mail.
8. **Legado** — contrato salvo antes da regra quebra ou cai num caminho diferente.
9. **Cadastro mudou** — pessoa inativa, rebaixada de sócio, área trocada depois do contrato.
10. **Regra só na tela** — o frontend barra, a API aceita. Não há teste de frontend neste
    projeto: uma regra que só existe na tela não fica travada por teste — diga isso.
11. **Regra concorrente em outra branch** — `git log origin/master` nos arquivos tocados: alguém
    já mudou a mesma regra?

### 4. Responda antes de mexer em código

Primeiro a resposta, em português simples, no formato abaixo. A pessoa decide o que corrigir.

```markdown
**Resposta curta:** [o que o sistema faz hoje, em uma ou duas frases]

| Cenário | O que acontece hoje | Evidência |
|---|---|---|
| Mônica marcada, sem %, com 20% geral | aceita; ficha mostra "Captação" sem dizer que vale 20% | `utils/participacao.py` → `linhas_participacao` |

**Buracos encontrados**
1. [nome do buraco] — [o que dá errado para quem usa] — [onde]

**O que eu travaria em teste** — [um teste por buraco, com o nome que vai ter]
**Sugestão de correção** — [curta; a decisão de regra é de quem pergunta]
```

Separe o que é **fato do código** do que é **decisão de negócio** ("sem valor, vale o geral ou
deve bloquear?"). Decisão de negócio vira pergunta, com a sua recomendação.

### 5. Trave os cenários em teste

Depois da resposta, escreva os testes dos buracos em `backend/tests/` (pytest; `conftest.py`
sobe um SQLite por teste). Um teste por cenário, com nome que conta a história
(`test_participante_sem_valor_proprio_mostra_que_vale_o_geral`), e docstring em uma linha dizendo
o caso.

Rode com o Python do venv do projeto (o venv da pasta `Codigo` tem um plugin de pytest quebrado),
a partir de `backend/`:

```bash
C:/Users/paollo/Downloads/Codigo/Honorario-cf/backend/.venv/Scripts/python.exe -m pytest -q tests/<arquivo>.py
```

**Mostre o teste vermelho.** Um teste escrito depois da correção tende a confirmar o presente e
não pegar o bug. Se o comportamento ainda está errado, o teste falha agora: mostre a falha. Se já
foi corrigido, reintroduza o bug e confirme que fica vermelho — acrescente a mutação em
`.claude/skills/contrato-cf/scripts/verifica_vermelho.py` para ela continuar sendo checada.

A correção só com o ok de quem perguntou. Depois dela: suíte inteira do backend, e se tocou no
frontend, `npx tsc --noEmit` e `npm run build` em `frontend/` (é o que o CI roda).

## Armadilhas deste ambiente

- A tela exige login Microsoft: para ver o comportamento em produção, peça para a pessoa logar no
  Chrome e use o Claude in Chrome; prévias de layout podem ser aplicadas na página via JavaScript,
  sem salvar nada.
- Produção não usa Alembic (não há `alembic_version`): coluna nova vai por DDL manual antes do
  deploy.
- Worktree nova para qualquer mudança; nunca troque a branch do checkout principal.
