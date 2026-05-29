# Fidelidade do Contrato ao Modelo (seções 4–11) + 2.4 visível — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reescrever o texto estático das seções 4–11 do gerador de contrato para reproduzir fielmente o modelo oficial, e exibir a cláusula 2.4 no front.

**Architecture:** O `ContractGenerator` monta o `.docx` por métodos `_add_*` que hoje emitem texto resumido. Substituímos o corpo desses métodos pelo texto canônico do spec, mantendo a lógica condicional (SEM/COM Parte Relacionada; tabela de êxito só com êxito). Frontend ganha um bloco read-only com o texto da 2.4.

**Tech Stack:** Python (python-docx, pytest), FastAPI/Pydantic; Next.js/React/TypeScript (frontend).

**Spec (fonte da verdade do texto):** `docs/superpowers/specs/2026-05-29-contrato-fidelidade-modelo-design.md`

---

## File Structure

- Modify: `backend/app/services/contract_generator.py`
  - `_add_common_clauses` (atual L750–799)
  - `_add_accessories` (L801–818)
  - `_add_obligations` (L820–835)
  - `_add_integrity` (L837–851)
  - `_add_term_and_termination` (L853–863)
  - `_add_ip` (L865–870)
  - `_add_general` (L872–887)
- Create: `backend/tests/test_contract_generator_fidelidade.py`
- Modify: `frontend/src/components/steps/Step2Escopo.tsx` (bloco 2.4 read-only)

**Helper de teste compartilhado** (definido na Task 1, reusado nas demais):
gera um contrato a partir de um dict e devolve a lista de parágrafos de texto.

---

## Task 1: Helper de teste + cláusulas comuns (seção 4)

**Files:**
- Create: `backend/tests/test_contract_generator_fidelidade.py`
- Modify: `backend/app/services/contract_generator.py` (`_add_common_clauses`)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_contract_generator_fidelidade.py
"""Garante que o contrato gerado reproduz o texto do modelo oficial (seções 4-11)."""
import re
import zipfile

from app.models.contract import ContratoRequest
from app.services.contract_generator import ContractGenerator


def _paras_for(req: dict) -> list[str]:
    """Gera o contrato e devolve os parágrafos de texto do .docx."""
    data = ContratoRequest(**req)
    gen = ContractGenerator()
    _, path = gen.generate(data, contract_id="FIDELIDADE_TEST")
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    paras = []
    for p in re.split(r"</w:p>", xml):
        txt = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p))
        if txt.strip():
            paras.append(txt.replace("&amp;", "&"))
    return paras


def _base_req(*, honorario="hora_trabalhada", extra_escopo=None, partes_rel=True) -> dict:
    escopo = {"tipo": "consultoria_lgpd", "honorarios": [honorario]}
    if honorario == "hora_trabalhada":
        escopo["hora_trabalhada"] = {
            "valor_hora": 300, "tem_teto_mensal": False, "tem_pacote_horas": False,
            "tem_hora_urgencia": False, "tem_hora_fora_expediente": False,
        }
    if extra_escopo:
        escopo.update(extra_escopo)
    return {
        "contratantes": [{
            "tipo": "PF", "nome": "Fulano", "nacionalidade": "brasileiro",
            "cpf": "00000000000", "profissao": "x", "estado_civil": "Solteiro(a)",
            "endereco": "rua x", "email": "a@a.com",
        }],
        "incluir_partes_relacionadas": partes_rel,
        "escopos": [escopo],
        "acessorios": {"tem_reembolso": True, "reembolso_limitado": False,
                       "tem_penalidade_inadimplemento": False},
        "participacao": {"tem_participacao": False},
    }


def _has(paras: list[str], needle: str) -> bool:
    return any(needle in p for p in paras)


def test_secao4_reforma_tributaria_e_fraude_completa():
    paras = _paras_for(_base_req())
    # 4.3 fraude com texto completo (canais oficiais)
    assert _has(paras, "canais oficiais de contato do C&F")
    # 4.7 reforma tributária
    assert _has(paras, "reforma tributária")
    assert _has(paras, "equilíbrio econômico-financeiro")
    # 4.8 faturamento fiscal eficiente
    assert _has(paras, "forma de faturamento mais eficiente do ponto de vista fiscal")


def test_secao4_solidariedade_com_parte_relacionada():
    # partes_rel=True + hora trabalhada => variante COM
    paras = _paras_for(_base_req(partes_rel=True))
    assert _has(paras, "assim como no caso de prestação de serviço a Partes Relacionadas")


def test_secao4_solidariedade_sem_parte_relacionada():
    paras = _paras_for(_base_req(partes_rel=False))
    assert _has(paras, "haverá solidariedade entre elas.")
    assert not _has(paras, "assim como no caso de prestação de serviço a Partes Relacionadas")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py -v`
Expected: FAIL (texto "reforma tributária", "canais oficiais de contato do C&F" ausentes).

- [ ] **Step 3: Substituir `_add_common_clauses` pela versão completa**

Substituir todo o método `_add_common_clauses` (atual L750–799) por:

```python
    def _add_common_clauses(self, doc: Document, data: ContratoRequest) -> None:
        doc.add_heading("4. CLÁUSULAS COMUNS AOS HONORÁRIOS", level=2)

        has_hora = any(TipoHonorario.HORA_TRABALHADA in e.honorarios for e in data.escopos)
        has_mensalidade_processo = any(
            TipoHonorario.MENSALIDADE in e.honorarios
            and e.mensalidade
            and e.mensalidade.subtipo in (SubtipoMensalidade.POR_PROCESSO, SubtipoMensalidade.POR_PASTA)
            for e in data.escopos
        )
        com_parte_relacionada = data.incluir_partes_relacionadas and (has_hora or has_mensalidade_processo)

        clauses = [
            "Todos os valores previstos nesta contratação serão reajustados anualmente "
            "pela variação positiva e acumulada do IPCA, ou outro índice que vier a "
            "substituí-lo, sempre desde a data da assinatura do Contrato.",
            "Todo e qualquer pagamento devido ao C&F será feito por meio de boleto bancário "
            f"ou transferência bancária para a conta de sua titularidade: {settings.bank_account_info}.",
            "A CONTRATANTE se declara ciente das notórias tentativas gerais de fraude e "
            "golpes simulando contatos de advogados e escritórios de advocacia, estando, "
            "contudo, igualmente ciente dos canais oficiais de contato do C&F e obrigando-se "
            "a realizar pagamentos somente em conta de titularidade do C&F ou mediante "
            "apresentação de boleto ou outro título em que este seja o beneficiário.",
            "A CONTRATANTE reconhece que qualquer pagamento realizado em inobservância ao "
            "previsto neste Contrato será considerado inválido e ineficaz.",
            "As obrigações de pagamento previstas neste Contrato serão devidas, independente "
            "de notificação, tão logo se dê o seu vencimento.",
            "O atraso no pagamento implicará na incidência do seguinte: juros de 1% a.m; "
            "multa de 10% (dez por cento) sobre o valor em atraso e atualização monetária "
            "pelo IPCA, sem prejuízo de suspensão do serviço ou rescisão contratual a "
            "critério do C&F.",
            "Em caso de mudanças legislativas/regulatórias relevantes (incluindo reforma "
            "tributária) que alterem substancialmente a carga tributária, os custos de "
            "conformidade, ou a forma de incidência/retenção de tributos aplicáveis aos "
            "serviços, as Partes renegociarão, de boa-fé, os valores e/ou a estrutura de "
            "faturamento para preservação do equilíbrio econômico-financeiro.",
            "A CONTRATANTE reconhece que o C&F poderá, dentro da legalidade e das normas "
            "aplicáveis, definir a forma de faturamento mais eficiente do ponto de vista "
            "fiscal (inclusive em eventual migração de regime tributário), sem alteração do "
            "escopo ou do valor líquido pactuado.",
        ]

        if com_parte_relacionada:
            clauses.append(
                "Caso qualificada mais de uma pessoa ou entidade no campo CONTRATANTE, "
                "haverá solidariedade entre elas, assim como no caso de prestação de "
                "serviço a Partes Relacionadas. Na hipótese de obrigações devidas ao C&F, "
                "as Partes reconhecem a possibilidade de encontro de contas, deduções e "
                "compensações ainda que multilaterais entre as partes signatárias e/ou "
                "Partes Relacionadas, de modo a adimplir tais obrigações em ordem "
                "preferencial."
            )
        else:
            clauses.append(
                "Caso qualificada mais de uma pessoa ou entidade no campo CONTRATANTE, "
                "haverá solidariedade entre elas. Na hipótese de obrigações devidas ao "
                "C&F, as Partes reconhecem a possibilidade de encontro de contas, deduções "
                "e compensações ainda que multilaterais entre as partes signatárias, de "
                "modo a adimplir tais obrigações em ordem preferencial."
            )

        for i, clause in enumerate(clauses, 1):
            doc.add_paragraph(f"4.{i}. {clause}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_contract_generator_fidelidade.py backend/app/services/contract_generator.py
git commit -m "feat(contrato): secao 4 clausulas comuns fiel ao modelo + condicional parte relacionada"
```

---

## Task 2: Reembolsos (seção 5)

**Files:**
- Modify: `backend/app/services/contract_generator.py` (`_add_accessories`)
- Test: `backend/tests/test_contract_generator_fidelidade.py`

- [ ] **Step 1: Write the failing test**

```python
def test_secao5_reembolsos_completos():
    paras = _paras_for(_base_req())
    assert _has(paras, "CredLocaliza")
    assert _has(paras, "R$ 1,70")
    assert _has(paras, "R$ 0,40")
    assert _has(paras, "honorários sucumbenciais fixados pertencem exclusivamente ao C&F")
    assert _has(paras, "multas processuais e/ou honorários de sucumbência")


def test_secao5_sem_reembolso_omite_51():
    req = _base_req()
    req["acessorios"]["tem_reembolso"] = False
    paras = _paras_for(req)
    assert not _has(paras, "no prazo de até 05 dias")
    # 5.2 e demais continuam presentes
    assert _has(paras, "CredLocaliza")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py::test_secao5_reembolsos_completos -v`
Expected: FAIL ("CredLocaliza" ausente).

- [ ] **Step 3: Substituir `_add_accessories`**

Substituir todo o método `_add_accessories` (atual L801–818) por:

```python
    def _add_accessories(self, doc: Document, ac: Acessorios) -> None:
        doc.add_heading("5. REEMBOLSOS, DESPESAS E OUTRAS VERBAS", level=2)
        counter = 1
        if ac.tem_reembolso:
            doc.add_paragraph(
                f"5.{counter}. Valores adiantados pelo C&F serão reembolsados pela "
                "CONTRATANTE, mediante comprovação, no prazo de até 05 dias após a "
                "apresentação do(s) comprovante(s)."
            )
            if ac.reembolso_limitado and ac.descricao_limitacao_reembolso:
                doc.add_paragraph(f"Limitação: {ac.descricao_limitacao_reembolso}")
            counter += 1

        clauses = [
            "Custas, despesas, taxas, emolumentos, cópias xerográficas, diligências, "
            "correspondentes, peritos, assistentes técnicos, tradutores, serviços de "
            "entrega e correio, deslocamentos, transporte, alimentação, hospedagem, demais "
            "despesas necessárias à execução do serviço e eventuais multas processuais e/ou "
            "honorários de sucumbência devidos ao advogado da parte contrária são de "
            "responsabilidade da CONTRATANTE.",
            "A CONTRATANTE reconhece que o C&F poderá utilizar ferramentas e/ou sistemas de "
            "busca de ativos, endereços e outras informações como CredLocaliza ou "
            "equivalentes, cujo custo será reembolsado pela CONTRATANTE nos exatos valores "
            "faturados pela ferramenta ou sistema.",
            "A prestação de serviço presencial fora da sede do C&F implicará em despesas de "
            "deslocamento, as quais serão cobradas à razão de R$ 1,70 (um real e setenta "
            "centavos) por quilômetro rodado.",
            "O custo de cada cópia xerox a ser reembolsado pela CONTRATANTE é de R$ 0,40 "
            "(quarenta centavos de reais).",
            "As Partes pactuam ainda que: (i) em caso de êxito, ainda que parcial, os "
            "honorários sucumbenciais fixados pertencem exclusivamente ao C&F; (ii) em caso "
            "de acordo que inclua renúncia a sucumbências, o C&F deverá ser previamente "
            "consultado; e (iii) se a CONTRATANTE concordar com a redução ou renúncia de "
            "sucumbências sem anuência do C&F, o valor correspondente será descontado do "
            "benefício econômico para fins de cálculo do êxito ou devido diretamente ao C&F.",
        ]
        for clause in clauses:
            doc.add_paragraph(f"5.{counter}. {clause}")
            counter += 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py -v`
Expected: PASS (todos os testes até agora).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/contract_generator.py backend/tests/test_contract_generator_fidelidade.py
git commit -m "feat(contrato): secao 5 reembolsos completos (CredLocaliza, km, xerox, sucumbencia)"
```

---

## Task 3: Obrigações (seção 6) + Integridade (seção 7)

**Files:**
- Modify: `backend/app/services/contract_generator.py` (`_add_obligations`, `_add_integrity`)
- Test: `backend/tests/test_contract_generator_fidelidade.py`

- [ ] **Step 1: Write the failing test**

```python
def test_secao6_obrigacoes_incisos_completos():
    paras = _paras_for(_base_req())
    assert _has(paras, "autorizar despesas quando exigido")
    assert _has(paras, "cooperar com o C&F na estratégia definida")
    assert _has(paras, "obrigação de meio")


def test_secao7_integridade_lgpd_e_ia():
    paras = _paras_for(_base_req())
    assert _has(paras, "tratar dados pessoais")
    assert _has(paras, "cadastros internos")
    assert _has(paras, "inteligência artificial")
    assert _has(paras, "diretrizes de Governança")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py::test_secao6_obrigacoes_incisos_completos -v`
Expected: FAIL ("autorizar despesas quando exigido" ausente).

- [ ] **Step 3: Substituir `_add_obligations` e `_add_integrity`**

Substituir `_add_obligations` (atual L820–835) por:

```python
    def _add_obligations(self, doc: Document) -> None:
        doc.add_heading("6. OBRIGAÇÕES DAS PARTES", level=2)
        doc.add_paragraph(
            "6.1. Obrigações da CONTRATANTE: (i) fornecer informações/documentos de forma "
            "completa e em tempo hábil; (ii) manter dados cadastrais atualizados; (iii) "
            "efetuar pagamentos dentro dos respectivos prazos; (iv) autorizar despesas "
            "quando exigido; (v) cooperar com o C&F na estratégia definida."
        )
        doc.add_paragraph(
            "6.2. Obrigações do C&F: (i) executar o serviço com diligência, técnica e zelo; "
            "(ii) manter confidencialidade e sigilo profissional; (iii) fornecer "
            "informações/documentos relativas à prestação de serviços, quando solicitado."
        )
        doc.add_paragraph(
            "6.3. A prestação de serviço advocatício constitui obrigação de meio, "
            "inexistindo obrigação de êxito e/ou resultado."
        )
```

Substituir `_add_integrity` (atual L837–851) por:

```python
    def _add_integrity(self, doc: Document) -> None:
        doc.add_heading("7. INTEGRIDADE E OUTROS", level=2)
        doc.add_paragraph(
            "7.1. As Partes comprometem-se a observar a legislação aplicável, incluindo Lei "
            "Anticorrupção e outras normas similares, bem como a cooperar com diretrizes de "
            "Governança, quando existentes e conhecidas, no que for pertinente à execução "
            "deste Contrato."
        )
        doc.add_paragraph(
            "7.2. As Partes comprometem-se a tratar dados pessoais estritamente para as "
            "finalidades deste Contrato, observando medidas razoáveis de segurança e "
            "confidencialidade, sendo autorizado desde já a criação de cadastros internos "
            "para fins de comunicação em geral."
        )
        doc.add_paragraph(
            "7.3. A CONTRATANTE declara estar ciente de que o C&F, sob supervisão humana, "
            "utiliza ferramentas de inteligência artificial e outras tecnologias como apoio "
            "à prestação do serviço."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/contract_generator.py backend/tests/test_contract_generator_fidelidade.py
git commit -m "feat(contrato): secoes 6-7 obrigacoes detalhadas + integridade (LGPD, IA, governanca)"
```

---

## Task 4: Prazo/Rescisão (seção 8) + tabela de êxito condicional

**Files:**
- Modify: `backend/app/services/contract_generator.py` (`_add_term_and_termination`, e a chamada em `_build_document` precisa passar `data`)
- Test: `backend/tests/test_contract_generator_fidelidade.py`

> Nota: `_add_term_and_termination` hoje recebe só `doc`. Precisa receber `data`
> para detectar êxito. Conferir a chamada em `_build_document` (atual L108):
> `self._add_term_and_termination(doc)` → `self._add_term_and_termination(doc, data)`.

- [ ] **Step 1: Write the failing test**

```python
def _req_com_exito() -> dict:
    return _base_req(honorario="exito", extra_escopo={"exito": {
        "subtipo": "percentual_fixo", "percentual": 20, "incidencia": "beneficio_economico",
        "base_calculo": "x", "vencimento": "a_vista", "forma_pagamento": "x",
        "tem_beneficio_prospectivo": False, "deduz_outro_honorario": False,
    }})


def test_secao8_rescisao_cpc_e_extincao():
    paras = _paras_for(_base_req())
    assert _has(paras, "art. 112, §1º, do Código de Processo Civil")
    assert _has(paras, "honorários vencidos serão devidos integralmente")


def test_secao8_tabela_exito_presente_com_exito():
    paras = _paras_for(_req_com_exito())
    assert _has(paras, "50% do percentual de êxito pactuado")
    assert _has(paras, "100% do percentual de êxito pactuado")
    assert _has(paras, "Antes da primeira decisão de mérito")
    assert _has(paras, "inocorrência de determinada fase processual")


def test_secao8_tabela_exito_ausente_sem_exito():
    paras = _paras_for(_base_req(honorario="hora_trabalhada"))
    assert not _has(paras, "50% do percentual de êxito pactuado")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py::test_secao8_rescisao_cpc_e_extincao -v`
Expected: FAIL ("art. 112, §1º" ausente).

- [ ] **Step 3: Ajustar a chamada em `_build_document` e substituir `_add_term_and_termination`**

Em `_build_document` (atual L108) trocar:
`self._add_term_and_termination(doc)` por `self._add_term_and_termination(doc, data)`.

Substituir `_add_term_and_termination` (atual L853–863) por:

```python
    def _add_term_and_termination(self, doc: Document, data: ContratoRequest) -> None:
        doc.add_heading("8. PRAZO, RESCISÃO E OUTROS EFEITOS", level=2)
        doc.add_paragraph(
            "8.1. Ressalvada a hipótese de prazo específico pactuado entre as Partes, o "
            "presente Contrato é celebrado por tempo indeterminado, até que seja esgotado o "
            "objeto contratado."
        )
        doc.add_paragraph(
            "8.2. Qualquer Parte poderá rescindir este Contrato imotivadamente mediante "
            "notificação por escrito com antecedência mínima de 30 (trinta) dias."
        )
        doc.add_paragraph(
            "8.2.1. Este prazo de antecedência não substitui nem prejudica o disposto nos "
            "art. 112, §1º, do Código de Processo Civil e 5º, §3º, do Estatuto da OAB, de "
            "modo que, no caso de demandas judiciais, arbitrais ou administrativos, o C&F e "
            "seus advogados permanecerão representando a CONTRATANTE durante os dez dias "
            "seguintes à notificação, salvo se forem substituídos antes do término desse "
            "prazo."
        )
        doc.add_paragraph(
            "8.3. Em caso de extinção contratual, aplica-se o seguinte: (i) honorários "
            "vencidos serão devidos integralmente; (ii) honorários vincendos pactuados por "
            "hora trabalhada serão devidos em relação aos serviços executados até a efetiva "
            "extinção; (iii) honorários vincendos pactuados por mensalidade serão devidos "
            "observando-se o prazo de antecedência de 30 dias previstos nesta cláusula; "
            "(iv) honorários vincendos pactuados por pró-labore serão devidos, "
            "proporcionalmente, observando-se os serviços executados e ainda não "
            "remunerados; (v) honorários de êxito vincendos ao momento da resilição "
            "continuarão devidos ao C&F observando-se a seguinte proporção não cumulativa:"
        )

        has_exito = any(TipoHonorario.EXITO in e.honorarios for e in data.escopos)
        next_clause = 4
        if has_exito:
            linhas = [
                ("Antes da primeira decisão de mérito", "50% do percentual de êxito pactuado"),
                ("Depois da primeira decisão de mérito e antes da primeira decisão recursal",
                 "70% do percentual de êxito pactuado"),
                ("Depois da primeira decisão recursal e antes do cumprimento ou liquidação "
                 "definitiva da decisão", "85% do percentual de êxito pactuado"),
                ("Durante cumprimento ou liquidação definitiva da decisão e antes do efetivo "
                 "proveito econômico", "95% do percentual de êxito pactuado"),
                ("Depois do efetivo proveito econômico", "100% do percentual de êxito pactuado"),
            ]
            table = doc.add_table(rows=1, cols=2)
            self._apply_table_grid(table)
            hdr = table.rows[0].cells
            hdr[0].text = "Fase processual em que for resilido o Contrato"
            hdr[1].text = "Honorário devido ao C&F"
            for fase, valor in linhas:
                row = table.add_row().cells
                row[0].text = fase
                row[1].text = valor
            doc.add_paragraph(
                "8.4. A eventual inocorrência de determinada fase processual não afeta o "
                "recebimento dos honorários de êxito nos termos previstos nesta cláusula, "
                "aplicando-se o percentual correspondente à fase processual ao tempo da "
                "resilição, independentemente da ocorrência das fases anteriores."
            )
            next_clause = 5

        doc.add_paragraph(
            f"8.{next_clause}. Exceto se expressa e diversamente pactuado, todas as "
            "disposições contratuais possuem validade e eficácia para os serviços já em "
            "curso."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/contract_generator.py backend/tests/test_contract_generator_fidelidade.py
git commit -m "feat(contrato): secao 8 rescisao (CPC art.112, extincao) + tabela exito condicional"
```

---

## Task 5: Propriedade Intelectual (9) + Disposições Gerais (10) + Foro (11)

**Files:**
- Modify: `backend/app/services/contract_generator.py` (`_add_ip`, `_add_general`)
- Test: `backend/tests/test_contract_generator_fidelidade.py`

- [ ] **Step 1: Write the failing test**

```python
def test_secao9_pi_uso_de_nome_marca():
    paras = _paras_for(_base_req())
    assert _has(paras, "vedada a disponibilização a terceiros")
    assert _has(paras, "utilizar seu nome, marca e logotipo")


def test_secao10_disposicoes_gerais_completas():
    paras = _paras_for(_base_req())
    assert _has(paras, "título executivo extrajudicial")
    assert _has(paras, "MP 2200-2")
    assert _has(paras, "deverá prevalecer em caso de dúvida")


def test_secao11_foro_com_renuncia():
    paras = _paras_for(_base_req())
    assert _has(paras, "com renúncia de qualquer outro, por mais privilegiado que seja")


def test_documento_termina_em_assinaturas():
    paras = _paras_for(_base_req())
    assert _has(paras, "TESTEMUNHAS:")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py::test_secao9_pi_uso_de_nome_marca -v`
Expected: FAIL ("utilizar seu nome, marca e logotipo" ausente).

- [ ] **Step 3: Substituir `_add_ip` e `_add_general`**

Substituir `_add_ip` (atual L865–870) por:

```python
    def _add_ip(self, doc: Document) -> None:
        doc.add_heading("9. PROPRIEDADE INTELECTUAL", level=2)
        doc.add_paragraph(
            "9.1. A produção intelectual (teses, estratégias, modelos, documentos, minutas "
            "e know-how) desenvolvida pelo C&F permanece de sua titularidade."
        )
        doc.add_paragraph(
            "9.2. Sem expressa autorização do C&F, é vedada a disponibilização a terceiros "
            "do conteúdo dessa produção intelectual (ainda que parcial), ressalvadas "
            "obrigações legais ou ordem de autoridade competente."
        )
        doc.add_paragraph(
            "9.3. É facultado ao C&F e aos advogados que o integram valerem-se dessa "
            "produção intelectual em livros, publicações e outras atuações profissionais, "
            "sempre com a ressalva de respeito ao sigilo das questões relacionadas a este "
            "Contrato."
        )
        doc.add_paragraph(
            "9.4. A CONTRATANTE autoriza o C&F a utilizar seu nome, marca e logotipo, de "
            "forma não exclusiva, para fins institucionais, inclusive em apresentações, "
            "portfólios e materiais correlatos, sem divulgação de informações confidenciais "
            "do serviço."
        )
```

Substituir `_add_general` (atual L872–887) por:

```python
    def _add_general(self, doc: Document) -> None:
        doc.add_heading("10. DISPOSIÇÕES GERAIS", level=2)
        gerais = [
            "Será considerada entregue a notificação e/ou comunicação encaminhada ao "
            "endereço declinado no preâmbulo deste Contrato, caso eventual alteração de "
            "contato ou endereço – inclusive eletrônico – não tenha sido devidamente "
            "comunicada ao C&F.",
            "Qualquer termo grafado com letra maiúscula neste Contrato deverá ter o "
            "significado nele previsto.",
            "As Partes se obrigam em caráter irrevogável e irretratável também por seus "
            "sucessores a qualquer título.",
            "Os direitos e obrigações decorrentes deste Contrato não poderão ser cedidos, "
            "salvo com expressa autorização das Partes signatárias.",
            "O não exercício, pelas Partes, de quaisquer dos direitos ou prerrogativas "
            "previstas neste Contrato, ou mesmo na legislação aplicável, será tido como ato "
            "de mera liberalidade, não constituindo alteração ou novação das obrigações ora "
            "estabelecidas, cujo cumprimento poderá ser exigido a qualquer tempo, "
            "independentemente de comunicação prévia à Parte.",
            "As Partes se comprometem a consultar uma à outra sempre que o não-exercício "
            "reiterado de eventual direito trouxer dúvida sobre eventual renúncia tácita, "
            "preferindo a manifestação expressa para a compreensão do comportamento alheio "
            "e formação de legítima confiança.",
            "O presente contrato é título executivo extrajudicial, podendo ser utilizado "
            "para a execução judicial de quaisquer obrigações nele constantes.",
            "Nos termos do artigo 10, § 2º da MP 2200-2/2001, § 4º do artigo 784 do Código "
            "de Processo Civil e legislação correlata, as Partes e as testemunhas aqui "
            "envolvidas reconhecem a validade de assinaturas eletrônicas ainda que não "
            "utilizem de certificado digital emitido pelo padrão ICP-Brasil.",
            "O Contrato terá efeito a partir da data indicada como aquela da sua "
            "formalização, independentemente de as assinaturas, eletrônicas ou não, serem "
            "eventualmente realizadas em data distinta.",
            "Eventual Proposta, feita pelo C&F e aceita pela CONTRATANTE, integra este "
            "Contrato, o qual, no entanto, deverá prevalecer em caso de dúvida, divergência "
            "ou conflito.",
        ]
        for i, clause in enumerate(gerais, 1):
            doc.add_paragraph(f"10.{i}. {clause}")

        doc.add_heading("11. FORO", level=2)
        doc.add_paragraph(
            "11.1. Fica eleito o foro da Comarca de Belo Horizonte/MG para dirimir "
            "quaisquer dúvidas ou controvérsias decorrentes deste Contrato, com renúncia de "
            "qualquer outro, por mais privilegiado que seja."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_contract_generator_fidelidade.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Rodar a suíte completa de geração pra garantir que nada quebrou**

Run: `cd backend && python -m pytest tests/test_bugfixes.py tests/test_send_for_signature.py tests/test_vencimento_recorrente.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/contract_generator.py backend/tests/test_contract_generator_fidelidade.py
git commit -m "feat(contrato): secoes 9-11 PI (nome/marca) + disposicoes gerais + foro fieis ao modelo"
```

---

## Task 6: Cláusula 2.4 visível no front (Step2Escopo)

**Files:**
- Modify: `frontend/src/components/steps/Step2Escopo.tsx` (bloco do toggle, atual L124–133)

- [ ] **Step 1: Adicionar bloco read-only condicional ao toggle**

No arquivo `frontend/src/components/steps/Step2Escopo.tsx`, localizar o bloco
(atual L124–133):

```tsx
      <div className="bg-card border border-border rounded-xl p-4 mt-4">
        <Toggle
          label="Inserir Cláusula de Partes Relacionadas (2.4)?"
          value={incluirPartesRelacionadas}
          onChange={onChangePartesRelacionadas}
        />
        <p className="text-xs text-muted ml-14">
          Aplicável quando a contratação envolver hora trabalhada ou honorário mensal por processo.
        </p>
      </div>
```

Substituir por (adiciona o texto da cláusula quando ligado):

```tsx
      <div className="bg-card border border-border rounded-xl p-4 mt-4">
        <Toggle
          label="Inserir Cláusula de Partes Relacionadas (2.4)?"
          value={incluirPartesRelacionadas}
          onChange={onChangePartesRelacionadas}
        />
        <p className="text-xs text-muted ml-14">
          Aplicável quando a contratação envolver hora trabalhada ou honorário mensal por processo.
        </p>
        {incluirPartesRelacionadas && (
          <div className="mt-3 ml-14 rounded-lg bg-muted/30 border border-border p-3 space-y-2">
            <p className="text-xs text-foreground">
              <strong>2.4.</strong> Para fins deste Contrato, são Partes Relacionadas: (i)
              cônjuge, companheiro(a) ou parente de primeiro ou segundo grau da CONTRATANTE;
              (ii) entidade(s) ou pessoa(s) jurídica(s) cujo controle fático ou jurídico seja
              da CONTRATANTE.
            </p>
            <p className="text-xs text-foreground">
              <strong>2.4.1.</strong> Caso a CONTRATANTE solicite atendimento a Partes
              Relacionadas, salvo ajuste expresso em contrário, serão aplicados os mesmos
              critérios de honorários previstos no Contrato, constituindo nova contratação
              para todos os fins.
            </p>
          </div>
        )}
      </div>
```

- [ ] **Step 2: Verificar build do frontend**

Run: `cd frontend && npm run build`
Expected: build OK, sem erros de TypeScript.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/steps/Step2Escopo.tsx
git commit -m "feat(front): exibir texto da clausula 2.4 quando toggle ligado"
```

---

## Self-Review (preenchido pelo autor do plano)

- **Cobertura do spec:** seções 4–11 → Tasks 1–5; 2.4 front → Task 6; condicional Parte Relacionada → Task 1; tabela êxito condicional → Task 4. ✅
- **Placeholders:** nenhum — todo texto canônico inline. ✅
- **Consistência de tipos:** `_add_term_and_termination(doc, data)` — chamada ajustada em `_build_document` (Task 4 Step 3). `has_exito`/`has_hora`/`has_mensalidade_processo` seguem o padrão já usado no arquivo. ✅
