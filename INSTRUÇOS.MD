```markdown
# Instruções Completas — Página `honorario-cf`

> **Objetivo:** Corrigir, padronizar e melhorar a interface de Contrato de Honorário do sistema Carvalho & Furtado Advogados.  
> **Destinatário:** Claude Code ou assistente de código.

---

## 1. Corrigir o link do logo no cabeçalho

**Problema:** O logo clicável no topo (`<a href="/">`) não leva a lugar nenhum.

**Ações:**
- Localize o componente do cabeçalho (layout global).
- Substitua `<a href="/">` pelo componente de navegação adequado à framework utilizada (ex.: `<Link to="/">` no React Router, `<NuxtLink to="/">` no Nuxt).
- Em aplicações tradicionais, verifique se não há `event.preventDefault()` ou `pointer-events: none` bloqueando o clique.
- Ao final, clique no logo → deve redirecionar para a raiz do sistema.

---

## 2. Substituir o logo inline pelo logo oficial do manual da marca

**Problema:** Logo atual é um SVG inline com texto. Deve ser a marca oficial.

**Ações:**
- Busque o arquivo de logo oficial nos diretórios de assets (`public/`, `assets/`, `static/`, etc.). Formatos esperados: `.svg`, `.png` ou `.webp`.
- Substitua o bloco SVG por:
  ```html
  <img src="/caminho/logo-oficial.svg" alt="Carvalho & Furtado Advogados" class="h-12 w-auto" />
  ```
- **Tamanho:** A altura (`h-12`, `h-14` etc.) deve ser **igual ou maior** que a do título “Contrato de Honorário” para manter equilíbrio visual.

---

## 3. Renomear “Sistema de honorários” para “Contrato de Honorário”

**Ações:**
- Busque no projeto (case-insensitive) por:
  - `Sistema de honorários`
  - `Sistema de Honorários`
  - `Sistema de honorarios`
- Substitua todas as ocorrências por **“Contrato de Honorário”**.
- Verifique títulos (`<h1>`), `<title>`, breadcrumbs, placeholders e metadados.

---

## 4. Revisão completa de acentuação

**Ações:**
- Faça uma varredura nos textos estáticos da página e dos componentes de layout associados (header, footer, sidebar).
- Garanta que palavras como “Advogados”, “Honorário” e quaisquer outras estejam corretamente acentuadas conforme o português.
- Corrija qualquer falta de acento encontrada.

---

## 5. Adicionar cláusula 2.4 – Partes Relacionadas

**Local:** Seção de Escopo do contrato.

**Texto:**
> **2.4 Partes Relacionadas:** Quando solicitado o serviço, os mesmos critérios de contratação serão aplicados a (i) cônjuge, companheiro(a) ou parente de primeiro ou segundo grau do cliente; (ii) entidade(s) ou pessoa(s) jurídica(s) cujo controle fático ou jurídico seja do cliente.

**Ações:**
- Insira o item após a cláusula 2.3. Se já existir 2.4, renumere as seguintes (2.4→2.5, 2.5→2.6 etc.).
- Mantenha a mesma formatação visual (fonte, margens, numeração) das demais cláusulas.

---

## 6. Campo “Natureza da participação” → lista suspensa (dropdown)

**Ações:**
- Substitua o campo atual por um `<select>` com as opções (nesta ordem):
  1. Captação
  2. Performance
  3. Captação e performance
  4. Projeto
  5. Outro
- Inclua uma opção inicial vazia (“Selecione…”).
- Mantenha a validação existente (obrigatório, se for o caso).
- O valor enviado ao backend deve ser a string da opção (ex.: `"Captação e performance"`).

---

## 7. Padronização dos campos de período e cálculo automático (todas as modalidades)

Esta seção substitui a lógica antiga de campo numérico para meses e introduz cálculo reativo para todas as modalidades de honorários que envolvam duração e/ou horas.

### 7.1 Campo de período por calendário (data de início e fim)

**Alvo:** Qualquer parte do formulário que peça “meses” ou duração do contrato (honorário fixo, compensação de horas, êxito, etc.).

**O que fazer:**
1. Identifique todas as ocorrências de campo numérico para “meses” ou “duração” e remova-as.
2. Adicione dois campos de data (date pickers) utilizando a biblioteca de componentes já presente no projeto (ex.: `shadcn/ui`, `Vuetify`, `Ant Design`):
   - **Data de início**
   - **Data de término**
   Ambos devem ser **somente leitura para digitação** (abrem apenas o calendário).
3. Crie um campo calculado e somente leitura **“Duração (meses)”** que exiba a diferença entre as datas em meses. Utilize uma lógica coerente:
   - Exemplo com `date-fns`: `differenceInMonths(dataFim, dataInicio) + 1` se a contagem incluir o mês inicial.
   - Exiba o valor inteiro ou com uma casa decimal, conforme necessidade do negócio.
4. Sempre que as datas mudarem, recalcule automaticamente.
5. **Validação:** Data de término deve ser maior ou igual à de início. Campos obrigatórios se o tipo de honorário exigir duração.

### 7.2 Cálculo automático de horas contratadas (onde aplicável)

**Alvo:** Modalidades que envolvem valor monetário e valor da hora (principalmente “Compensação de horas”, mas também qualquer outra que venha a usar essa lógica).

**O que fazer:**
1. Para cada modalidade que tiver os campos:
   - **Valor total (R$)** – que pode ser:  
     - `tetoMensal × duraçãoMeses` (para compensação)  
     - um valor fixo inserido pelo usuário  
   - **Valor da hora (R$)** – que pode ser um parâmetro fixo do escritório (buscar de configuração) ou editável por contrato. Confirme com o usuário.
2. Calcule:  
   `horasContratadas = valorTotal / valorHora`
3. Exiba o resultado em campo **somente leitura**, formatado com até duas casas decimais e separador de milhar.
4. Esse cálculo deve funcionar em **todas as modalidades** onde houver combinação de valor/hora, não apenas em “Compensação de horas”.

### 7.3 Saldo de horas (horas contratadas vs. horas trabalhadas)

1. Adicione um campo **“Horas já trabalhadas”** (numérico, manual, valor inicial 0) se não houver integração automática com timesheet. Esse campo deve ser editável conforme permissão (definir com o usuário).
2. Calcule:  
   `saldoHoras = horasContratadas - horasTrabalhadas`
3. Exiba a informação:
   - Se `saldoHoras > 0`: “Saldo positivo: X horas”
   - Se `saldoHoras < 0`: “Horas excedidas: X horas”
   - Se `saldoHoras === 0`: “Horas integralmente utilizadas”
4. Atualize automaticamente sempre que qualquer campo relacionado mudar.

---

## 8. Atualização do payload do formulário

- Certifique-se de que os novos campos sejam enviados ao backend:
  - `dataInicio` (formato ISO ou dd/MM/yyyy conforme API)
  - `dataFim`
  - `duracaoMeses` (calculado)
  - `horasContratadas` (calculado)
  - `horasTrabalhadas` (editável)
- Verifique os nomes esperados pela API (analise contratos existentes ou pergunte ao usuário).
- Se a modalidade de honorário não exigir duração ou horas, esses campos podem ser omitidos ou enviados como `null`.

---

## 9. Testes de aceitação

1. Acesse a página `honorario-cf`.
2. Crie um novo contrato e selecione qualquer modalidade que peça duração.
   - Selecione data de início 01/06/2026 e data de término 31/08/2026.
   - O campo “Duração (meses)” deve exibir **3 meses** (ou valor esperado).
3. Altere para “Compensação de horas”.
   - Preencha teto mensal = R$ 5.000, datas resultando em 3 meses, valor da hora = R$ 9.
   - O campo “Horas contratadas” deve mostrar **1.666,67**.
   - Insira “Horas já trabalhadas” = 1000 → Saldo positivo: **666,67 horas**.
4. Teste as validações (data fim < data início, campos obrigatórios vazios).
5. Verifique a reatividade ao alterar datas ou valores.
6. Submeta o formulário e confirme que o payload contém todos os novos campos corretamente.

---

## Dúvidas para confirmação (antes de codar)

1. Qual a biblioteca de componentes do projeto (date picker)? Isso define a implementação do calendário.
2. O valor da hora é um parâmetro fixo do escritório (constante ou vindo de uma configuração) ou pode variar por contrato?
3. O cálculo de meses deve considerar meses exatos (diferença de dias ÷ 30) ou meses do calendário (ex.: de 15/jan a 14/fev = 1 mês)?
4. O backend já suporta os campos `dataInicio`, `dataFim`, `duracaoMeses`, `horasContratadas`, `horasTrabalhadas`? Quais os nomes exatos esperados?
5. O campo “Horas já trabalhadas” será de uso temporário até uma integração futura? Há restrição de permissão para editá-lo?

---

**Após esclarecidas as dúvidas, execute todas as seções (1 a 8) e realize os testes conforme a seção 9.**
```   