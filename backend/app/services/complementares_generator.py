"""Geradores de aditivo, distrato e substabelecimento (issue #126).

Reaproveitam o layout e a grade de assinaturas (tags do DocuSeal) do contrato de
consumidor. O texto vem literal dos modelos do escritorio; as clausulas
condicionais e os dados variaveis estao nos metodos de cada tipo. Os dados dos
modelos de referencia (clientes, valores, processos) nao entram no codigo.
"""

from __future__ import annotations

from datetime import date, datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.models.documentos_complementares import (
    AditivoRequest,
    DistratoRequest,
    SubstabelecimentoRequest,
    nome_contratante,
)
from app.services.consumidor_generator import ConsumidorGenerator
from app.services.contract_generator import MESES_PT_BR
from app.utils.currency import numero_com_extenso, valor_com_extenso

ESCRITORIO_NOME = "CARVALHO & FURTADO ADVOGADOS"
ESCRITORIO_CNPJ = "25.463.159/0001-73"
ESCRITORIO_OAB = "OAB/MG sob o n.º 125"
ESCRITORIO_ENDERECO = "Rua Antônio de Albuquerque, n.º 271, 5º andar, Savassi, Belo Horizonte/MG, CEP 30.112-010"
LOCAL = "Belo Horizonte/MG"


def _sem_ponto(texto: str) -> str:
    return texto.strip().rstrip(".;, ")


def _mes_ano(iso: str | None) -> str:
    """'2025-06-10' -> 'junho de 2025'."""
    d = _data(iso)
    return f"{MESES_PT_BR[d.month - 1]} de {d.year}"


def _data(iso: str | None) -> date:
    try:
        return date.fromisoformat((iso or "")[:10])
    except ValueError:
        return date.today()


class ComplementarGenerator(ConsumidorGenerator):
    """Base: titulo centralizado, corpo do tipo, fechamento com data e assinaturas."""

    TITULO = ""

    def _build_document(self, data, signatario_roles: list[dict] | None = None) -> Document:  # type: ignore[override]
        doc = self._new_document_from_template()
        self._clear_body(doc)
        self._clear_headers_footers(doc)
        self._ensure_contract_styles(doc)

        titulo = doc.add_heading(self._titulo(data), level=1)
        titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._corpo(doc, data)
        self._fechamento(doc, data, signatario_roles)
        self._apply_document_standard(doc)
        return doc

    # Cada tipo implementa estes tres.
    def _titulo(self, data) -> str:
        return self.TITULO

    def _corpo(self, doc: Document, data) -> None:
        raise NotImplementedError

    def _fechamento(self, doc: Document, data, signatario_roles: list[dict] | None) -> None:
        raise NotImplementedError

    # ── Partes ────────────────────────────────────────────────────

    @staticmethod
    def _cnpj_cpf(c: dict) -> str:
        if c.get("cnpj"):
            return f"inscrita no CNPJ sob o n.º {c['cnpj']}"
        return f"inscrito(a) no CPF sob o n.º {c.get('cpf', '')}"

    def _qualificar(self, c: dict, *, com_representantes: bool = True) -> str:
        """Qualificacao do contratante a partir do form_data do contrato de origem."""
        nome = nome_contratante(c).upper()
        if c.get("cnpj"):
            partes = [nome, "pessoa jurídica de direito privado", self._cnpj_cpf(c)]
            if c.get("endereco"):
                partes.append(f"com sede em {c['endereco']}")
            reps = [r for r in (c.get("representantes") or []) if r.get("nome")] if com_representantes else []
            if reps:
                partes.append(
                    "neste ato representada por "
                    + "; e por ".join(
                        ", ".join(filter(None, [r["nome"].upper(), f"CPF {r['cpf']}" if r.get("cpf") else None]))
                        for r in reps
                    )
                )
            return ", ".join(partes)
        partes = [nome, c.get("nacionalidade"), c.get("estado_civil"), c.get("profissao"), self._cnpj_cpf(c)]
        if c.get("endereco"):
            partes.append(f"residente em {c['endereco']}")
        return ", ".join(p for p in partes if p)

    def _data_extenso(self, iso: str | None) -> str:
        d = _data(iso)
        return self._format_date_pt_br(datetime.combine(d, datetime.min.time()))

    # ── Fechamento ────────────────────────────────────────────────

    def _data_e_local(self, doc: Document, data) -> None:
        doc.add_paragraph()
        doc.add_paragraph(f"{LOCAL}, {self._data_extenso(data.data_documento)}.")
        doc.add_paragraph()

    def _assinaturas_partes(self, doc: Document, data, signatario_roles: list[dict] | None) -> None:
        """Contratante(s) e escritorio (+ testemunhas) — aditivo e distrato."""
        entries: list[tuple[str, list[str]]] = []
        if signatario_roles:
            for sig in (s for s in signatario_roles if s.get("role", "").startswith("Contratante")):
                nome = sig.get("name", "Contratante")
                entries.append((
                    f"{{{{Assinatura {nome};type=signature;role={sig['role']}}}}}",
                    [nome.upper(), "Contratante"],
                ))
            for sig in (s for s in signatario_roles if s.get("role", "").startswith("Contratado")):
                entries.append((
                    f"{{{{Assinatura {ESCRITORIO_NOME.title()};type=signature;role={sig['role']}}}}}",
                    [ESCRITORIO_NOME, f"CNPJ n.º {ESCRITORIO_CNPJ}", "Contratada"],
                ))
        else:
            unico = len(data.contratantes) == 1
            for i, c in enumerate(data.contratantes, 1):
                nome = nome_contratante(c)
                role = "Contratante" if unico else f"Contratante {i}"
                doc_ = c.get("cnpj") or c.get("cpf") or ""
                rotulo = [nome.upper(), f"{'CNPJ' if c.get('cnpj') else 'CPF'} n.º {doc_}", "Contratante"]
                entries.append((f"{{{{Assinatura {nome};type=signature;role={role}}}}}", rotulo))
            entries.append((
                "{{Assinatura Contratada;type=signature;role=Contratado}}",
                [ESCRITORIO_NOME, f"CNPJ n.º {ESCRITORIO_CNPJ}", "Contratada"],
            ))
        self._grid_assinaturas(doc, entries)

        testemunhas = [s for s in (signatario_roles or []) if s.get("role", "").startswith("Testemunha")]
        doc.add_paragraph()
        doc.add_paragraph("Testemunhas:")
        if testemunhas:
            self._grid_assinaturas(doc, [
                (
                    f"{{{{Assinatura {s.get('name', 'Testemunha')};type=signature;role={s['role']}}}}}",
                    [f"{s['role'].upper()}: {s.get('name', 'Testemunha').upper()}"],
                )
                for s in testemunhas
            ])
        else:
            doc.add_paragraph()
            doc.add_paragraph("Nome:")
            doc.add_paragraph("CPF n.º")
            doc.add_paragraph()
            doc.add_paragraph("Nome:")
            doc.add_paragraph("CPF n.º")


class AditivoGenerator(ComplementarGenerator):
    def _titulo(self, data: AditivoRequest) -> str:
        prefixo = f"{data.numero}º " if data.numero > 1 else ""
        return f"{prefixo}ADITIVO CONTRATUAL AO CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS"

    def _corpo(self, doc: Document, data: AditivoRequest) -> None:
        doc.add_paragraph("Pelo presente instrumento particular, de um lado:")
        for c in data.contratantes:
            doc.add_paragraph(f"{self._qualificar(c)}.")
        doc.add_paragraph("E, de outro lado:")
        doc.add_paragraph(
            f"{ESCRITORIO_NOME}, pessoa jurídica de direito interno, sociedade simples de prestação de "
            f"serviços advocatícios, inscrita no CNPJ n.º {ESCRITORIO_CNPJ}, com sede na {ESCRITORIO_ENDERECO}."
        )

        # Considerandos: contrato de origem, aditivos anteriores e o atual.
        ano = _data(data.data_contrato_origem).year
        doc.add_paragraph("Considerando que:")
        doc.add_paragraph(f"As partes firmaram Contrato de Prestação de Serviços Advocatícios em {ano};")
        for ant in data.aditivos_anteriores:
            doc.add_paragraph(
                f"Em {_mes_ano(ant.data_documento)}, as partes firmaram o {ant.numero}º Aditivo "
                f"Contratual, tendo por objeto {_sem_ponto(ant.objeto)};"
            )
        ordinal = f"{data.numero}º " if data.numero > 1 else ""
        doc.add_paragraph(
            f"Em {_mes_ano(data.data_documento)}, as partes acordaram o presente aditivo, "
            f"tendo por objeto {_sem_ponto(data.objeto)};"
        )
        doc.add_paragraph(
            f"Resolvem firmar o presente {ordinal}Aditivo Contratual, que se regerá pelas cláusulas e "
            "condições seguintes:"
        )

        n = 0

        def clausula(titulo: str) -> None:
            nonlocal n
            n += 1
            doc.add_heading(f"Cláusula {n} – {titulo}", level=2)

        clausula("Objeto")
        doc.add_paragraph(
            f"O presente aditivo tem por objeto a formalização de {_sem_ponto(data.objeto)}."
        )

        r = data.remuneracao
        clausula("Remuneração")
        doc.add_paragraph(
            f"Pelos serviços objeto deste aditivo, o CONTRATANTE pagará ao CONTRATADO o valor fixo "
            f"mensal de {valor_com_extenso(r.valor_mensal)}, correspondente a uma franquia de "
            f"{numero_com_extenso(r.franquia_horas, 'horas')} mensais de trabalho."
        )
        doc.add_paragraph(
            f"Parágrafo único: O valor da hora excedente será de {valor_com_extenso(r.valor_hora_excedente)}."
        )

        if data.compensacao_anual:
            clausula("Compensação e Faturamento")
            doc.add_paragraph(
                "Será admitida a compensação de horas entre os meses, com apuração do saldo (crédito ou "
                "débito) ao final de cada período de 12 (doze) meses da contratação."
            )
            doc.add_paragraph(
                "§1º – A apuração será acompanhada do envio de fatura discriminada e boleto bancário para "
                "pagamento à vista."
            )

        if data.abrangencia:
            clausula("Abrangência")
            empresas = [
                f"{nome_contratante(c).upper()}, inscrita no CNPJ sob o n.º {c['cnpj']}"
                for c in data.contratantes if c.get("cnpj")
            ] + [f"{e.razao_social.upper()}, inscrita no CNPJ sob o n.º {e.cnpj}" for e in data.abrangencia]
            lista = "; ".join(empresas[:-1]) + f" e {empresas[-1]}" if len(empresas) > 1 else empresas[0]
            doc.add_paragraph(
                "A prestação dos serviços objeto deste aditivo abrangerá as pessoas jurídicas inscritas sob "
                f"os respectivos CNPJs: {lista}."
            )

        clausula("Ratificação")
        doc.add_paragraph(
            "Permanecem inalteradas as demais cláusulas e condições do contrato original, que continuam "
            "em pleno vigor."
        )
        doc.add_paragraph(
            "E, por estarem assim justas e contratadas, firmam o presente aditivo em 2 (duas) vias de "
            "igual teor e forma, para um só efeito."
        )

    def _fechamento(self, doc: Document, data: AditivoRequest, signatario_roles) -> None:
        self._data_e_local(doc, data)
        self._assinaturas_partes(doc, data, signatario_roles)


class DistratoGenerator(ComplementarGenerator):
    TITULO = "DISTRATO AO CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS"

    def _corpo(self, doc: Document, data: DistratoRequest) -> None:
        doc.add_paragraph("São Partes:")
        for c in data.contratantes:
            doc.add_paragraph(
                f"{self._qualificar(c, com_representantes=False)}, neste ato representada na forma de seu Contrato Social, "
                'doravante denominada simplesmente "CONTRATANTE"; e'
            )
        doc.add_paragraph(
            f"{ESCRITORIO_NOME}, pessoa jurídica de direito privado, sociedade simples de prestação de "
            f"serviços advocatícios, inscrita no CNPJ sob o n.º {ESCRITORIO_CNPJ}, estabelecida na "
            f"{ESCRITORIO_ENDERECO}, neste ato representada na forma de seu Contrato Social, doravante "
            'denominada simplesmente "CONTRATADA";'
        )
        doc.add_paragraph(
            'CONTRATANTE e CONTRATADA serão, quando denominadas individualmente, "PARTE" e, '
            'coletivamente, "PARTES".'
        )

        doc.add_paragraph("CONSIDERANDO QUE:")
        considerandos = [
            f"As Partes celebraram, em {self._data_extenso(data.data_contrato_origem)}, o Contrato de "
            "Prestação de Serviços Advocatícios, tendo por objeto a prestação de serviços de "
            f"{_sem_ponto(data.objeto_contrato_origem)};"
        ]
        for ant in data.aditivos_anteriores:
            considerandos.append(
                f"As Partes celebraram, em {_mes_ano(ant.data_documento)}, o {ant.numero}º Aditivo "
                f"Contratual ao referido Contrato, tendo por objeto {_sem_ponto(ant.objeto)};"
            )
        considerandos.append(
            "É de comum interesse das Partes rescindir e extinguir formalmente a referida relação "
            "contratual, nos termos do art. 472 do Código Civil;"
        )
        for i, texto in enumerate(considerandos, 1):
            doc.add_paragraph(f"{_romano(i)}. {texto}")

        doc.add_paragraph(
            "Resolvem as Partes firmar o presente DISTRATO AO CONTRATO DE PRESTAÇÃO DE SERVIÇOS "
            "ADVOCATÍCIOS, que se regerá pelas seguintes cláusulas e condições:"
        )

        doc.add_heading("CLÁUSULA PRIMEIRA – DO DISTRATO", level=2)
        doc.add_paragraph(
            "1.1. As Partes acordam expressamente com o encerramento e rescisão definitiva do Contrato de "
            f"Prestação de Serviços Advocatícios firmado em {self._data_extenso(data.data_contrato_origem)}, "
            "assim o fazendo sem a incidência de qualquer ônus, penalidade, multa rescisória ou "
            "indenização de parte a parte."
        )
        doc.add_paragraph(
            "1.2. As Partes reconhecem que o objeto da prestação de serviços sob responsabilidade da "
            "CONTRATADA foi executado a contento e que os valores devidos pela CONTRATANTE a título de "
            "honorários fixos e eventuais despesas foram integralmente adimplidos a tempo e modo."
        )

        doc.add_heading("CLÁUSULA SEGUNDA – DA QUITAÇÃO E REVOGAÇÃO DE PODERES", level=2)
        if data.ressalva_exito:
            alcance = (
                "seja a título de honorários fixos, reembolsos ou indenizações, ressalvados os honorários "
                "de êxito eventualmente devidos em razão de demandas em curso, que permanecem exigíveis "
                "nos termos do contrato originário"
            )
        else:
            alcance = "seja a título de honorários fixos, reembolsos, indenizações ou honorários de êxito futuros"
        doc.add_paragraph(
            "2.1. Por este instrumento, as Partes concedem-se reciprocamente plena, geral, rasa, "
            "irrestrita e irrevogável quitação de todas as obrigações principais, acessórias, diretas e "
            "indiretas decorrentes do contrato originário e de eventuais aditivos celebrados, nada mais "
            f"tendo a reclamar ou exigir uma da outra, {alcance}, em juízo ou fora dele."
        )
        if data.substabelecer_e_devolver:
            doc.add_paragraph(
                "2.2. A CONTRATADA compromete-se a substabelecer sem reserva de poderes a favor do novo "
                "patrono a ser indicado pela CONTRATANTE, bem como a restituir eventuais documentos "
                "físicos ou digitais que estejam sob sua guarda."
            )

        doc.add_paragraph(
            "E, por estarem justas e acordadas, as Partes firmam o presente instrumento em 2 (duas) vias "
            "de igual teor e forma, na presença de 2 (duas) testemunhas abaixo assinadas, para que "
            "produza todos os seus jurídicos e legais efeitos."
        )

    def _fechamento(self, doc: Document, data: DistratoRequest, signatario_roles) -> None:
        self._data_e_local(doc, data)
        self._assinaturas_partes(doc, data, signatario_roles)


class SubstabelecimentoGenerator(ComplementarGenerator):
    TITULO = "SUBSTABELECIMENTO SEM RESERVA DE PODERES"

    @staticmethod
    def _qualificar_substabelecido(s) -> str:
        f = s.genero == "F"
        nacionalidade = s.nacionalidade.strip() or ("brasileira" if f else "brasileiro")
        return (
            f"{'Dra.' if f else 'Dr.'} {s.nome}, {nacionalidade}, {s.estado_civil}, "
            f"{'inscrita' if f else 'inscrito'} na {s.oab}"
        )

    def _corpo(self, doc: Document, data: SubstabelecimentoRequest) -> None:
        substabelecentes = "; ".join(f"{s.nome.upper()}, {s.oab}" for s in data.substabelecentes)
        substabelecidos = "; ".join(self._qualificar_substabelecido(s) for s in data.substabelecidos)
        doc.add_paragraph(
            f"Pelo presente instrumento, {substabelecentes}, substabelecem, SEM RESERVA DE PODERES, aos "
            f"advogados {substabelecidos}, todos com endereço profissional à "
            f"{_sem_ponto(data.endereco_substabelecidos)}, os poderes que lhe foram conferidos por "
            f"{data.outorgante.exibicao}, no âmbito dos processos judiciais abaixo indicados, seus "
            "incidentes, desdobramentos e recursos correlatos, ressalvados os honorários contratuais e "
            "sucumbenciais:"
        )
        for p in data.processos:
            sufixo = f" – {_sem_ponto(p.descricao)}" if p.descricao.strip() else ""
            doc.add_paragraph(f"{p.classe} n.º {p.numero}{sufixo}.")
        doc.add_paragraph(
            "Os efeitos do presente substabelecimento se estendem a todos os patronos cujos poderes foram "
            "outorgados à época que possuíam vínculo com o escritório Carvalho & Furtado Advogados, "
            f"inscrita no CNPJ n.º {ESCRITORIO_CNPJ} e na {ESCRITORIO_OAB}, com sede na Rua Antônio de "
            "Albuquerque, 271, 5º andar, Savassi, Belo Horizonte/MG, CEP 30.112-010."
        )

    def _fechamento(self, doc: Document, data: SubstabelecimentoRequest, signatario_roles) -> None:
        self._data_e_local(doc, data)
        if signatario_roles:
            sigs = [s for s in signatario_roles if s.get("role", "").startswith("Substabelecente")]
            por_email = {s.email.lower(): s for s in data.substabelecentes}
            entries = []
            for sig in sigs:
                nome = sig.get("name", "Substabelecente")
                cadastro = por_email.get((sig.get("email") or "").lower())
                rotulo = [nome.upper()] + ([cadastro.oab] if cadastro else []) + ["Substabelecente"]
                entries.append((f"{{{{Assinatura {nome};type=signature;role={sig['role']}}}}}", rotulo))
        else:
            unico = len(data.substabelecentes) == 1
            entries = [
                (
                    f"{{{{Assinatura {s.nome};type=signature;role="
                    f"{'Substabelecente' if unico else f'Substabelecente {i}'}}}}}",
                    [s.nome.upper(), s.oab, "Substabelecente"],
                )
                for i, s in enumerate(data.substabelecentes, 1)
            ]
        self._grid_assinaturas(doc, entries)


def _romano(n: int) -> str:
    out = ""
    for valor, letra in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= valor:
            out += letra
            n -= valor
    return out
