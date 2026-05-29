# Fidelidade do contrato gerado ao modelo oficial (seções 4–11) + 2.4 visível

**Data:** 2026-05-29
**Status:** Aprovado (design)
**Fonte da verdade:** `2026 Contrato de Honorários Modelo Padrão.docx` (raiz do repo `Codigo`)

## Problema

O `contract_generator.py` produz uma versão **condensada e incompleta** do
contrato. O `.docx` não trava — ele simplesmente omite cláusulas e encurta
textos a partir da seção "CLÁUSULAS COMUNS AOS HONORÁRIOS". Cláusulas inteiras
do modelo oficial não aparecem (reforma tributária, sucumbência, CPC art. 112,
tabela de êxito por fase, uso de nome/marca, título executivo, MP 2200-2 etc.).

Repro confirmou que o gerador emite ~7 cláusulas na seção 4 onde o modelo tem
~14, e versões resumidas das seções 5–11.

## Objetivo

Reescrever o **texto estático** das seções 4–11 do gerador para reproduzir
**fielmente** o modelo oficial, mantendo a lógica condicional já existente, e
**exibir o texto da cláusula 2.4 no front** (Step2).

## Decisões (brainstorming)

- **Numeração sequencial limpa** (4,5,6,7…) — não espelhar a numeração
  inconsistente do modelo (que pula 7→11→12→13→10.1→14→15).
- **Tabela de êxito por fase** (rescisão): incluir **só quando houver honorário
  de êxito** no contrato.
- Marcações "APLICÁVEL QUANDO…" do modelo são **instruções de template** →
  viram **condicionais no código**, nunca texto literal no contrato.
- 2.4: condição atual do código está correta (modelo: "aplicável quando hora
  trabalhada OU honorário mensal por processo E selecionada previsão de Partes
  Relacionadas"). Texto usa **"da CONTRATANTE"** (modelo), não "cliente".

## Escopo

- **Dentro:** seções 4–11 do `contract_generator.py`
  (`_add_common_clauses`, `_add_accessories`, `_add_obligations`,
  `_add_integrity`, `_add_term_and_termination`, `_add_ip`, `_add_general`,
  foro) + exibição de 2.4 no front `Step2Escopo.tsx`.
- **Fora:** seções 1–3 (partes, objeto/tabela, disposições de honorário) — o
  usuário não reportou problema nelas. `bank_account_info` já bate com o modelo.

## Texto canônico (numeração limpa do gerador)

> Onde o modelo usa `C&F`, manter `C&F`. Onde há valor de conta, usar
> `{settings.bank_account_info}` (já = "Banco Inter - Ag. 0001 c/c 17841983-4
> ou Pix 25463159000173").

### 4. CLÁUSULAS COMUNS AOS HONORÁRIOS

4.1. Todos os valores previstos nesta contratação serão reajustados anualmente
pela variação positiva e acumulada do IPCA, ou outro índice que vier a
substituí-lo, sempre desde a data da assinatura do Contrato.

4.2. Todo e qualquer pagamento devido ao C&F será feito por meio de boleto
bancário ou transferência bancária para a conta de sua titularidade:
{settings.bank_account_info}.

4.3. A CONTRATANTE se declara ciente das notórias tentativas gerais de fraude e
golpes simulando contatos de advogados e escritórios de advocacia, estando,
contudo, igualmente ciente dos canais oficiais de contato do C&F e obrigando-se
a realizar pagamentos somente em conta de titularidade do C&F ou mediante
apresentação de boleto ou outro título em que este seja o beneficiário.

4.4. A CONTRATANTE reconhece que qualquer pagamento realizado em inobservância
ao previsto neste Contrato será considerado inválido e ineficaz.

4.5. As obrigações de pagamento previstas neste Contrato serão devidas,
independente de notificação, tão logo se dê o seu vencimento.

4.6. O atraso no pagamento implicará na incidência do seguinte: juros de 1%
a.m; multa de 10% (dez por cento) sobre o valor em atraso e atualização
monetária pelo IPCA, sem prejuízo de suspensão do serviço ou rescisão
contratual a critério do C&F.

4.7. Em caso de mudanças legislativas/regulatórias relevantes (incluindo
reforma tributária) que alterem substancialmente a carga tributária, os custos
de conformidade, ou a forma de incidência/retenção de tributos aplicáveis aos
serviços, as Partes renegociarão, de boa-fé, os valores e/ou a estrutura de
faturamento para preservação do equilíbrio econômico-financeiro.

4.8. A CONTRATANTE reconhece que o C&F poderá, dentro da legalidade e das normas
aplicáveis, definir a forma de faturamento mais eficiente do ponto de vista
fiscal (inclusive em eventual migração de regime tributário), sem alteração do
escopo ou do valor líquido pactuado.

**4.9. Solidariedade — CONDICIONAL** (`com_parte_relacionada` = mesma condição
da 2.4):
- **SEM Parte Relacionada:** "Caso qualificada mais de uma pessoa ou entidade no
  campo CONTRATANTE, haverá solidariedade entre elas. Na hipótese de obrigações
  devidas ao C&F, as Partes reconhecem a possibilidade de encontro de contas,
  deduções e compensações ainda que multilaterais entre as partes signatárias,
  de modo a adimplir tais obrigações em ordem preferencial."
- **COM Parte Relacionada:** "Caso qualificada mais de uma pessoa ou entidade no
  campo CONTRATANTE, haverá solidariedade entre elas, assim como no caso de
  prestação de serviço a Partes Relacionadas. Na hipótese de obrigações devidas
  ao C&F, as Partes reconhecem a possibilidade de encontro de contas, deduções e
  compensações ainda que multilaterais entre as partes signatárias e/ou Partes
  Relacionadas, de modo a adimplir tais obrigações em ordem preferencial."

### 5. REEMBOLSOS, DESPESAS E OUTRAS VERBAS

5.1. *(só se `tem_reembolso`)* Valores adiantados pelo C&F serão reembolsados
pela CONTRATANTE, mediante comprovação, no prazo de até 05 dias após a
apresentação do(s) comprovante(s). *(se `reembolso_limitado` →
"Limitação: {descricao_limitacao_reembolso}")*

5.2. Custas, despesas, taxas, emolumentos, cópias xerográficas, diligências,
correspondentes, peritos, assistentes técnicos, tradutores, serviços de entrega
e correio, deslocamentos, transporte, alimentação, hospedagem, demais despesas
necessárias à execução do serviço e eventuais multas processuais e/ou
honorários de sucumbência devidos ao advogado da parte contrária são de
responsabilidade da CONTRATANTE.

5.3. A CONTRATANTE reconhece que o C&F poderá utilizar ferramentas e/ou sistemas
de busca de ativos, endereços e outras informações como CredLocaliza ou
equivalentes, cujo custo será reembolsado pela CONTRATANTE nos exatos valores
faturados pela ferramenta ou sistema.

5.4. A prestação de serviço presencial fora da sede do C&F implicará em despesas
de deslocamento, as quais serão cobradas à razão de R$ 1,70 (um real e setenta
centavos) por quilômetro rodado.

5.5. O custo de cada cópia xerox a ser reembolsado pela CONTRATANTE é de R$ 0,40
(quarenta centavos de reais).

5.6. As Partes pactuam ainda que: (i) em caso de êxito, ainda que parcial, os
honorários sucumbenciais fixados pertencem exclusivamente ao C&F; (ii) em caso
de acordo que inclua renúncia a sucumbências, o C&F deverá ser previamente
consultado; e (iii) se a CONTRATANTE concordar com a redução ou renúncia de
sucumbências sem anuência do C&F, o valor correspondente será descontado do
benefício econômico para fins de cálculo do êxito ou devido diretamente ao C&F.

### 6. OBRIGAÇÕES DAS PARTES

6.1. Obrigações da CONTRATANTE: (i) fornecer informações/documentos de forma
completa e em tempo hábil; (ii) manter dados cadastrais atualizados; (iii)
efetuar pagamentos dentro dos respectivos prazos; (iv) autorizar despesas quando
exigido; (v) cooperar com o C&F na estratégia definida.

6.2. Obrigações do C&F: (i) executar o serviço com diligência, técnica e zelo;
(ii) manter confidencialidade e sigilo profissional; (iii) fornecer
informações/documentos relativas à prestação de serviços, quando solicitado.

6.3. A prestação de serviço advocatício constitui obrigação de meio, inexistindo
obrigação de êxito e/ou resultado.

### 7. INTEGRIDADE E OUTROS

7.1. As Partes comprometem-se a observar a legislação aplicável, incluindo Lei
Anticorrupção e outras normas similares, bem como a cooperar com diretrizes de
Governança, quando existentes e conhecidas, no que for pertinente à execução
deste Contrato.

7.2. As Partes comprometem-se a tratar dados pessoais estritamente para as
finalidades deste Contrato, observando medidas razoáveis de segurança e
confidencialidade, sendo autorizado desde já a criação de cadastros internos
para fins de comunicação em geral.

7.3. A CONTRATANTE declara estar ciente de que o C&F, sob supervisão humana,
utiliza ferramentas de inteligência artificial e outras tecnologias como apoio à
prestação do serviço.

### 8. PRAZO, RESCISÃO E OUTROS EFEITOS

8.1. Ressalvada a hipótese de prazo específico pactuado entre as Partes, o
presente Contrato é celebrado por tempo indeterminado, até que seja esgotado o
objeto contratado.

8.2. Qualquer Parte poderá rescindir este Contrato imotivadamente mediante
notificação por escrito com antecedência mínima de 30 (trinta) dias.

8.2.1. Este prazo de antecedência não substitui nem prejudica o disposto nos
art. 112, §1º, do Código de Processo Civil e 5º, §3º, do Estatuto da OAB, de modo
que, no caso de demandas judiciais, arbitrais ou administrativos, o C&F e seus
advogados permanecerão representando a CONTRATANTE durante os dez dias seguintes
à notificação, salvo se forem substituídos antes do término desse prazo.

8.3. Em caso de extinção contratual, aplica-se o seguinte: (i) honorários
vencidos serão devidos integralmente; (ii) honorários vincendos pactuados por
hora trabalhada serão devidos em relação aos serviços executados até a efetiva
extinção; (iii) honorários vincendos pactuados por mensalidade serão devidos
observando-se o prazo de antecedência de 30 dias previstos nesta cláusula; (iv)
honorários vincendos pactuados por pró-labore serão devidos, proporcionalmente,
observando-se os serviços executados e ainda não remunerados; (v) honorários de
êxito vincendos ao momento da resilição continuarão devidos ao C&F observando-se
a seguinte proporção não cumulativa:

**Tabela de êxito por fase — CONDICIONAL (só se houver honorário de êxito no
contrato).** Tabela 2 colunas (Fase processual | Honorário devido ao C&F):

| Fase processual em que for resilido o Contrato | Honorário devido ao C&F |
|---|---|
| Antes da primeira decisão de mérito | 50% do percentual de êxito pactuado |
| Depois da primeira decisão de mérito e antes da primeira decisão recursal | 70% do percentual de êxito pactuado |
| Depois da primeira decisão recursal e antes do cumprimento ou liquidação definitiva da decisão | 85% do percentual de êxito pactuado |
| Durante cumprimento ou liquidação definitiva da decisão e antes do efetivo proveito econômico | 95% do percentual de êxito pactuado |
| Depois do efetivo proveito econômico | 100% do percentual de êxito pactuado |

8.4. *(só se houver êxito)* A eventual inocorrência de determinada fase
processual não afeta o recebimento dos honorários de êxito nos termos previstos
nesta cláusula, aplicando-se o percentual correspondente à fase processual ao
tempo da resilição, independentemente da ocorrência das fases anteriores.

8.5. Exceto se expressa e diversamente pactuado, todas as disposições
contratuais possuem validade e eficácia para os serviços já em curso.

### 9. PROPRIEDADE INTELECTUAL

9.1. A produção intelectual (teses, estratégias, modelos, documentos, minutas e
know-how) desenvolvida pelo C&F permanece de sua titularidade.

9.2. Sem expressa autorização do C&F, é vedada a disponibilização a terceiros do
conteúdo dessa produção intelectual (ainda que parcial), ressalvadas obrigações
legais ou ordem de autoridade competente.

9.3. É facultado ao C&F e aos advogados que o integram valerem-se dessa produção
intelectual em livros, publicações e outras atuações profissionais, sempre com a
ressalva de respeito ao sigilo das questões relacionadas a este Contrato.

9.4. A CONTRATANTE autoriza o C&F a utilizar seu nome, marca e logotipo, de
forma não exclusiva, para fins institucionais, inclusive em apresentações,
portfólios e materiais correlatos, sem divulgação de informações confidenciais
do serviço.

### 10. DISPOSIÇÕES GERAIS

10.1. Será considerada entregue a notificação e/ou comunicação encaminhada ao
endereço declinado no preâmbulo deste Contrato, caso eventual alteração de
contato ou endereço – inclusive eletrônico – não tenha sido devidamente
comunicada ao C&F.

10.2. Qualquer termo grafado com letra maiúscula neste Contrato deverá ter o
significado nele previsto.

10.3. As Partes se obrigam em caráter irrevogável e irretratável também por seus
sucessores a qualquer título.

10.4. Os direitos e obrigações decorrentes deste Contrato não poderão ser
cedidos, salvo com expressa autorização das Partes signatárias.

10.5. O não exercício, pelas Partes, de quaisquer dos direitos ou prerrogativas
previstas neste Contrato, ou mesmo na legislação aplicável, será tido como ato
de mera liberalidade, não constituindo alteração ou novação das obrigações ora
estabelecidas, cujo cumprimento poderá ser exigido a qualquer tempo,
independentemente de comunicação prévia à Parte.

10.6. As Partes se comprometem a consultar uma à outra sempre que o
não-exercício reiterado de eventual direito trouxer dúvida sobre eventual
renúncia tácita, preferindo a manifestação expressa para a compreensão do
comportamento alheio e formação de legítima confiança.

10.7. O presente contrato é título executivo extrajudicial, podendo ser
utilizado para a execução judicial de quaisquer obrigações nele constantes.

10.8. Nos termos do artigo 10, § 2º da MP 2200-2/2001, § 4º do artigo 784 do
Código de Processo Civil e legislação correlata, as Partes e as testemunhas aqui
envolvidas reconhecem a validade de assinaturas eletrônicas ainda que não
utilizem de certificado digital emitido pelo padrão ICP-Brasil.

10.9. O Contrato terá efeito a partir da data indicada como aquela da sua
formalização, independentemente de as assinaturas, eletrônicas ou não, serem
eventualmente realizadas em data distinta.

10.10. Eventual Proposta, feita pelo C&F e aceita pela CONTRATANTE, integra este
Contrato, o qual, no entanto, deverá prevalecer em caso de dúvida, divergência ou
conflito.

### 11. FORO

11.1. Fica eleito o foro da Comarca de Belo Horizonte/MG para dirimir quaisquer
dúvidas ou controvérsias decorrentes deste Contrato, com renúncia de qualquer
outro, por mais privilegiado que seja.

## 2.4 visível no front (Step2Escopo.tsx)

Abaixo do toggle "Inserir Cláusula de Partes Relacionadas (2.4)?", quando
**ligado**, exibir um bloco read-only com o texto da cláusula:

> 2.4. Para fins deste Contrato, são Partes Relacionadas: (i) cônjuge,
> companheiro(a) ou parente de primeiro ou segundo grau da CONTRATANTE; (ii)
> entidade(s) ou pessoa(s) jurídica(s) cujo controle fático ou jurídico seja da
> CONTRATANTE.
> 2.4.1. Caso a CONTRATANTE solicite atendimento a Partes Relacionadas, salvo
> ajuste expresso em contrário, serão aplicados os mesmos critérios de honorários
> previstos no Contrato, constituindo nova contratação para todos os fins.

Manter a dica de aplicabilidade ("Aplicável quando a contratação envolver hora
trabalhada ou honorário mensal por processo").

## Testes (TDD)

- Backend `test_contract_generator_fidelidade.py` (novo): gerar contrato e
  extrair parágrafos; asserir presença literal das cláusulas-chave que faltavam
  (4.7 reforma tributária, 5.3 CredLocaliza, 5.6 sucumbência, 6.1 incisos (iv)(v),
  7.2 LGPD, 8.2.1 CPC art.112, 9.4 nome/marca, 10.7 título executivo, 10.8 MP
  2200-2, 11.1 renúncia de foro).
- Condicional êxito: contrato **com** êxito inclui as 5 linhas da tabela;
  contrato **sem** êxito não inclui.
- Condicional Parte Relacionada: texto 4.9 alterna SEM/COM conforme a regra.
- Sanidade: documento continua bem-formado (XML válido) e termina nas
  assinaturas/testemunhas.

## Fora de escopo

- Não muda cálculo de honorários nem seções 1–3.
- Não altera numeração para espelhar o modelo (mantém sequencial limpa).
