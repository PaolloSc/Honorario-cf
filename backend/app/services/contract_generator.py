from __future__ import annotations
 
import os
import tempfile
import uuid
import zipfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
 
from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
 
from app.config import BACKEND_DIR, settings
from app.models.contract import (
    Acessorios,
    ContratantePF,
    ContratantePJ,
    ContratoRequest,
    ESCOPO_LABELS,
    EscopoItem,
    Participacao,
    SubtipoExito,
    SubtipoMensalidade,
    TipoEscopo,
    TipoHonorario,
    TipoPessoa,
    VariacaoPrecoMensalidade,
)
from app.utils.currency import formatar_valor, valor_com_extenso, valor_por_extenso
 

INCIDENCIA_EXITO_LABELS = {
    "beneficio_economico": "benefício econômico",
    "beneficio_financeiro": "benefício financeiro",
    "beneficio_tributario": "benefício tributário",
    "todos": "todos os benefícios",
}

FORMA_PAGAMENTO_LABELS = {
    "a_vista": "à vista",
    "parcelado": "parcelado",
    "conforme_cumprimento": "conforme cumprimento",
}

HONORARIO_LABELS = {
    "pro_labore": "pró-labore",
    "mensalidade": "mensalidade",
    "hora_trabalhada": "hora trabalhada",
}

MESES_PT_BR = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

 
class ContractGenerator:
    def __init__(self) -> None:
        self.template_path = self._resolve_backend_path(settings.template_path)
        self.output_dir = self._resolve_backend_path(settings.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
 
    def generate(self, data: ContratoRequest) -> tuple[str, str]:
        """Generate a contract document from form data.
 
        Returns (contract_id, file_path).
        """
        contract_id = str(uuid.uuid4())
        doc = self._build_document(data)
 
        filename = f"contrato_{contract_id}.docx"
        filepath = self.output_dir / filename
        doc.save(str(filepath))
 
        return contract_id, str(filepath)
 
    def _build_document(self, data: ContratoRequest) -> Document:
        doc = self._new_document_from_template()
        self._clear_body(doc)
        self._ensure_contract_styles(doc)
 
        self._add_title(doc)
        self._add_parties(doc, data)
        self._add_scope_and_fees(doc, data)
        self._add_fee_details(doc, data)
        self._add_common_clauses(doc)
        self._add_accessories(doc, data.acessorios)
        self._add_obligations(doc)
        self._add_integrity(doc)
        self._add_term_and_termination(doc)
        self._add_ip(doc)
        self._add_general(doc)
        self._add_signatures(doc, data)
        self._apply_document_standard(doc)
 
        return doc

    def _resolve_backend_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return BACKEND_DIR / path

    def _new_document_from_template(self) -> DocxDocument:
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template de contrato nao encontrado: {self.template_path}")

        if self.template_path.suffix.lower() == ".dotx":
            return self._document_from_dotx(self.template_path)

        return Document(str(self.template_path))

    def _document_from_dotx(self, dotx_path: Path) -> DocxDocument:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        tmp_path = Path(tmp.name)
        tmp.close()

        try:
            with zipfile.ZipFile(dotx_path, "r") as src, zipfile.ZipFile(tmp_path, "w") as dst:
                for item in src.infolist():
                    content = src.read(item.filename)
                    if item.filename == "[Content_Types].xml":
                        content = content.replace(
                            b"application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml",
                            b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
                        )
                    dst.writestr(item, content)

            return Document(str(tmp_path))
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    def _clear_body(self, doc: DocxDocument) -> None:
        body = doc._element.body
        for element in list(body):
            if element.tag != qn("w:sectPr"):
                body.remove(element)

    def _ensure_contract_styles(self, doc: DocxDocument) -> None:
        if "List Bullet" not in doc.styles:
            bullet_style = doc.styles.add_style("List Bullet", WD_STYLE_TYPE.PARAGRAPH)
            bullet_style.base_style = doc.styles["Normal"]
            bullet_style.paragraph_format.left_indent = Cm(0.5)

        for level in (1, 2, 3):
            style_name = f"Heading {level}"
            if style_name in doc.styles:
                style = doc.styles[style_name]
            else:
                style = doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)

            style.base_style = doc.styles["Normal"]
            style.font.name = "Segoe UI"
            style._element.rPr.rFonts.set(qn("w:eastAsia"), "Segoe UI")
            style.font.size = Pt(12)
            style.font.bold = True
            style.font.color.rgb = RGBColor(0, 0, 0)
            style.paragraph_format.line_spacing = 1.15
            style.paragraph_format.space_after = Pt(6)

    def _apply_document_standard(self, doc: DocxDocument) -> None:
        self._apply_page_setup(doc)
        self._apply_base_styles(doc)
        self._ensure_page_number_footer(doc)

        for paragraph in doc.paragraphs:
            self._format_paragraph(paragraph)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        self._format_paragraph(paragraph)

    def _apply_page_setup(self, doc: DocxDocument) -> None:
        for section in doc.sections:
            section.top_margin = Cm(3)
            section.left_margin = Cm(3)
            section.bottom_margin = Cm(2)
            section.right_margin = Cm(2)

    def _apply_base_styles(self, doc: DocxDocument) -> None:
        for style_name in ("Normal", "Body Text", "List Paragraph"):
            if style_name not in doc.styles:
                continue
            style = doc.styles[style_name]
            style.font.name = "Segoe UI"
            style._element.rPr.rFonts.set(qn("w:eastAsia"), "Segoe UI")
            style.font.size = Pt(12)
            style.font.color.rgb = RGBColor(0, 0, 0)
            style.paragraph_format.line_spacing = 1.15
            style.paragraph_format.space_after = Pt(6)

    def _format_paragraph(self, paragraph) -> None:
        is_heading = paragraph.style and paragraph.style.name.startswith("Heading")
        is_signature = self._is_signature_paragraph(paragraph.text)

        paragraph.paragraph_format.line_spacing = 1.15
        paragraph.paragraph_format.space_after = Pt(0 if is_signature else 6)

        for run in paragraph.runs:
            if is_heading:
                run.text = run.text.upper()
            run.font.name = "Segoe UI"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "Segoe UI")
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0, 0, 0)
            if is_heading:
                run.bold = True

    def _ensure_page_number_footer(self, doc: DocxDocument) -> None:
        for section in doc.sections:
            footer = section.footer
            if "PAGE" in footer._element.xml:
                continue

            paragraph = footer.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = paragraph.add_run()
            self._add_page_number_field(run)

    def _add_page_number_field(self, run) -> None:
        begin = OxmlElement("w:fldChar")
        begin.set(qn("w:fldCharType"), "begin")

        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = "PAGE"

        separate = OxmlElement("w:fldChar")
        separate.set(qn("w:fldCharType"), "separate")

        text = OxmlElement("w:t")
        text.text = "1"

        end = OxmlElement("w:fldChar")
        end.set(qn("w:fldCharType"), "end")

        run._r.extend([begin, instr, separate, text, end])

    def _is_signature_paragraph(self, text: str) -> bool:
        stripped = text.strip()
        return stripped.startswith("_") or stripped in {"Nome:", "CPF:", "TESTEMUNHAS:"}

    def _format_vencimento(self, value: str | None, *, recorrente: bool = False) -> str:
        raw = (value or "").strip()
        if not raw:
            return "a definir"

        digits = "".join(ch for ch in raw if ch.isdigit())
        if recorrente and raw.isdigit():
            return f"no dia {int(raw)} de cada mês"

        if len(digits) == 8:
            return f"em {digits[:2]}/{digits[2:4]}/{digits[4:]}"

        return raw

    def _format_percentual(self, value: float) -> str:
        if float(value).is_integer():
            return f"{int(value)}%"
        return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",") + "%"

    def _label_from_map(self, value: str | None, labels: dict[str, str]) -> str:
        raw = (value or "").strip()
        return labels.get(raw, raw)

    def _format_date_pt_br(self, value: datetime) -> str:
        return f"{value.day:02d} de {MESES_PT_BR[value.month - 1]} de {value.year}"

    def _apply_table_grid(self, table) -> None:
        tbl_pr = table._tbl.tblPr
        borders = tbl_pr.first_child_found_in("w:tblBorders")
        if borders is None:
            borders = OxmlElement("w:tblBorders")
            tbl_pr.append(borders)

        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            tag = f"w:{edge}"
            element = borders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                borders.append(element)
            element.set(qn("w:val"), "single")
            element.set(qn("w:sz"), "4")
            element.set(qn("w:space"), "0")
            element.set(qn("w:color"), "000000")
 
    def _add_title(self, doc: Document) -> None:
        title = doc.add_heading("CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS", level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
 
    def _add_parties(self, doc: Document, data: ContratoRequest) -> None:
        doc.add_heading("1. DAS PARTES", level=2)
 
        for i, contratante in enumerate(data.contratantes, 1):
            if isinstance(contratante, ContratantePJ) or (
                isinstance(contratante, dict) and contratante.get("tipo") == "PJ"
            ):
                c = contratante if isinstance(contratante, ContratantePJ) else ContratantePJ(**contratante)
                text = (
                    f"CONTRATANTE {i}: {c.razao_social}, inscrita no CNPJ n. {c.cnpj}, "
                    f"com sede em {c.endereco}, e-mail: {c.email}."
                )
                if c.representante_nome:
                    text += (
                        f" Representada por {c.representante_nome}, "
                        f"{c.representante_nacionalidade or ''}, "
                        f"{c.representante_profissao or ''}, "
                        f"{c.representante_estado_civil.value if c.representante_estado_civil else ''}, "
                        f"CPF {c.representante_cpf or ''}, "
                        f"e-mail: {c.representante_email or ''}."
                    )
            else:
                c = contratante if isinstance(contratante, ContratantePF) else ContratantePF(**contratante)
                text = (
                    f"CONTRATANTE {i}: {c.nome}, {c.nacionalidade}, "
                    f"{c.profissao}, {c.estado_civil.value}, "
                    f"CPF {c.cpf}, residente em {c.endereco}, "
                    f"e-mail: {c.email}."
                )
            doc.add_paragraph(text)
 
        doc.add_paragraph(
            "CONTRATADO: CARVALHO & FURTADO ADVOGADOS, sociedade simples de advocacia, "
                "inscrita no CNPJ n. 25.463.159/0001-73, com sede na Rua Antônio de Albuquerque, "
                "n. 271, 5º andar, Savassi, Belo Horizonte/MG, doravante denominado C&F."
        )
 
        if data.incluir_partes_relacionadas:
            doc.add_heading("1.1. Partes Relacionadas", level=3)
            doc.add_paragraph(
                "Para fins deste Contrato, são Partes Relacionadas: (i) cônjuge, "
                "companheiro(a) ou parente de primeiro ou segundo grau da CONTRATANTE; "
                "(ii) entidade(s) ou pessoa(s) jurídica(s) cujo controle fático ou jurídico "
                "pertença à CONTRATANTE ou às pessoas físicas referidas no item (i)."
            )
            doc.add_paragraph(
                "Caso a CONTRATANTE solicite atendimento a Partes Relacionadas, salvo ajuste "
                "expresso em contrário, serão aplicados os mesmos critérios de honorários "
                "previstos no Contrato, constituindo nova contratação para todos os fins."
            )
 
    def _add_scope_and_fees(self, doc: Document, data: ContratoRequest) -> None:
        doc.add_heading("2. OBJETO, ESCOPO E HONORÁRIO", level=2)
 
        doc.add_paragraph(
            '2.1. O objeto do presente Contrato ("Contrato") é a prestação, pelo C&F, '
            "de serviços advocatícios à CONTRATANTE, conforme o seguinte Escopo e Preço:"
        )
 
        # Summary table
        table = doc.add_table(rows=1, cols=2)
        self._apply_table_grid(table)
        hdr = table.rows[0].cells
        hdr[0].text = "Escopo"
        hdr[1].text = "Preço"
 
        for escopo in data.escopos:
            row = table.add_row().cells
            row[0].text = self._escopo_description(escopo)
            row[1].text = self._preco_resumo(escopo)
 
        doc.add_paragraph()
 
        doc.add_paragraph(
            "2.2. Não estão incluídos no escopo: serviços contábeis, perícias, cálculos, "
            "auditorias, análise econômica, financeira ou de qualquer outra natureza que "
            "não seja estritamente jurídica."
        )
 
        has_hora = any(TipoHonorario.HORA_TRABALHADA in e.honorarios for e in data.escopos)
        has_mensalidade_partido = any(
            TipoHonorario.MENSALIDADE in e.honorarios
            and e.mensalidade
            and e.mensalidade.subtipo == SubtipoMensalidade.ADVOCACIA_PARTIDO
            for e in data.escopos
        )
 
        if has_hora:
            doc.add_paragraph(
                "Caso a CONTRATANTE solicite atendimento a questões expressamente não "
                "indicadas no objeto e escopo deste Contrato, serão aplicados os mesmos "
                "critérios de honorários de hora trabalhada previstos no Contrato."
            )
        else:
            doc.add_paragraph(
                "2.3. Não estão incluídos na precificação serviços oferecidos pelo C&F "
                "e não expressamente indicados no objeto e escopo deste Contrato, os quais "
                "poderão ser pactuados posteriormente entre as Partes."
            )
 
        if has_mensalidade_partido:
            doc.add_paragraph(
                "Também não estão incluídos na precificação os serviços de consultoria que "
                "constituam um projeto específico multidisciplinar ou dotado de certa "
                "complexidade, tais como planejamentos e/ou estruturações."
            )
 
    def _add_fee_details(self, doc: Document, data: ContratoRequest) -> None:
        doc.add_heading("3. OUTRAS DISPOSIÇÕES SOBRE HONORÁRIOS", level=2)
 
        for escopo in data.escopos:
            for tipo_hon in escopo.honorarios:
                if tipo_hon == TipoHonorario.HORA_TRABALHADA and escopo.hora_trabalhada:
                    self._add_hora_trabalhada(doc, escopo.hora_trabalhada)
                elif tipo_hon == TipoHonorario.PRO_LABORE and escopo.pro_labore:
                    self._add_pro_labore(doc, escopo.pro_labore)
                elif tipo_hon == TipoHonorario.MENSALIDADE and escopo.mensalidade:
                    self._add_mensalidade(doc, escopo.mensalidade)
                elif tipo_hon == TipoHonorario.EXITO and escopo.exito:
                    self._add_exito(doc, escopo.exito)
                elif tipo_hon == TipoHonorario.PERMUTA and escopo.permuta:
                    self._add_permuta(doc, escopo.permuta)
 
    def _add_hora_trabalhada(self, doc: Document, ht: "HoraTrabalhada") -> None:
        doc.add_heading("HORA TRABALHADA", level=3)
        doc.add_paragraph("Em relação ao honorário por hora trabalhada, será observado o seguinte:")
 
        doc.add_paragraph(
            f"O valor da hora trabalhada será de {valor_com_extenso(ht.valor_hora)}.",
            style="List Bullet",
        )
        doc.add_paragraph(
            "As horas trabalhadas serão apuradas ao final de cada mês e faturadas em "
            "parcela única no mês imediatamente subsequente.",
            style="List Bullet",
        )
 
        if ht.tem_hora_urgencia:
            doc.add_paragraph(
                "As horas trabalhadas serão acrescidas de percentual de 50% (cinquenta por cento) "
                "quando, por solicitação da CONTRATANTE, os serviços forem prestados em regime "
                "de urgência.",
                style="List Bullet",
            )
 
        if ht.tem_hora_fora_expediente:
            doc.add_paragraph(
                "Caso a CONTRATANTE demande a prestação dos serviços após as 19:00 horas ou "
                "durante finais de semana ou feriados, as horas trabalhadas serão acrescidas "
                "do percentual de 100% (cem por cento).",
                style="List Bullet",
            )
 
        if ht.tem_hora_urgencia and ht.tem_hora_fora_expediente:
            doc.add_paragraph(
                "Caso as horas sejam de urgência e prestadas fora do expediente, serão cobradas "
                "com acréscimo de 150%.",
                style="List Bullet",
            )
 
        if ht.tem_teto_mensal and ht.valor_teto_mensal:
            doc.add_paragraph(
                f"A fatura mensal das horas trabalhadas respeitará o teto de "
                f"{valor_com_extenso(ht.valor_teto_mensal)}, de modo que o valor excedente "
                f"será cobrado na(s) fatura(s) subsequente(s) respeitando o referido teto.",
                style="List Bullet",
            )
 
        if ht.tem_pacote_horas and ht.quantidade_horas_pacote and ht.valor_pacote:
            doc.add_paragraph(
                f"Os serviços jurídicos serão remunerados mediante pacote mensal fixo de "
                f"{ht.quantidade_horas_pacote} horas, no valor de "
                f"{valor_com_extenso(ht.valor_pacote)}.",
                style="List Bullet",
            )
            doc.add_paragraph(
                f"As horas não utilizadas em determinado mês serão acumuladas e poderão ser "
                f"aproveitadas no mês imediatamente subsequente.",
                style="List Bullet",
            )
            if ht.periodo_banco_horas_meses:
                doc.add_paragraph(
                    f"O saldo acumulado será zerado a cada {ht.periodo_banco_horas_meses} meses.",
                    style="List Bullet",
                )
 
    def _add_pro_labore(self, doc: Document, pl: "ProLabore") -> None:
        doc.add_heading("PRO-LABORE", level=3)
        doc.add_paragraph("Em relação ao honorário pró-labore, será observada a seguinte forma de pagamento:")
 
        if pl.tem_parcelamento and pl.numero_parcelas and pl.valor_parcela:
            doc.add_paragraph(
                f"O valor total de {valor_com_extenso(pl.valor_total)} será pago em "
                f"{pl.numero_parcelas} parcelas de {valor_com_extenso(pl.valor_parcela)}, "
                f"com vencimento {self._format_vencimento(pl.vencimento_parcelas, recorrente=True)}."
            )
        else:
            doc.add_paragraph(
                f"O valor de {valor_com_extenso(pl.valor_total)} será pago em parcela única, "
                f"com vencimento {self._format_vencimento(pl.vencimento)}."
            )
 
    def _add_mensalidade(self, doc: Document, m: "Mensalidade") -> None:
        if m.subtipo == SubtipoMensalidade.ADVOCACIA_PARTIDO:
            doc.add_heading("MENSALIDADE DE ADVOCACIA DE PARTIDO", level=3)
            doc.add_paragraph(
                "Em relação ao honorário por mensalidade de advocacia de partido, "
                "será observado o seguinte:"
            )
            doc.add_paragraph(
                "O honorário abrange a prestação de serviços advocatícios de consultoria "
                "e contencioso de rotina nas áreas oferecidas pelo C&F.",
                style="List Bullet",
            )
            doc.add_paragraph(
                "A precificação possui como referência o fluxo atual de demanda da "
                "CONTRATANTE, sendo que o honorário deverá ser renegociado caso esse "
                "fluxo aumente.",
                style="List Bullet",
            )
            doc.add_paragraph(
                f"O valor da mensalidade será de {valor_com_extenso(m.valor)}.",
                style="List Bullet",
            )
            doc.add_paragraph(
                f"O vencimento da fatura mensal será {self._format_vencimento(m.dia_vencimento, recorrente=True)}.",
                style="List Bullet",
            )
 
        elif m.subtipo in (SubtipoMensalidade.POR_PROCESSO, SubtipoMensalidade.POR_PASTA):
            tipo_label = "processo" if m.subtipo == SubtipoMensalidade.POR_PROCESSO else "pasta"
            doc.add_heading(f"MENSALIDADE POR {tipo_label.upper()}", level=3)
 
            var_label = ""
            if m.variacao_preco == VariacaoPrecoMensalidade.LIMITACAO_TEMPORAL:
                var_label = " com limitação temporal"
            elif m.variacao_preco == VariacaoPrecoMensalidade.REDUCAO_VOLUME:
                var_label = " com redução por volume"
            elif m.variacao_preco == VariacaoPrecoMensalidade.VARIACAO_FASE_PROCESSUAL:
                var_label = " com variação por fase processual"
 
            doc.add_paragraph(
                f"Em relação ao honorário por mensalidade{var_label}, o vencimento "
                f"da fatura será {self._format_vencimento(m.dia_vencimento, recorrente=True)} "
                f"e o valor de {valor_com_extenso(m.valor)} será devido por {tipo_label} enquanto este "
                f"estiver ativo."
            )
 
            if m.variacao_preco == VariacaoPrecoMensalidade.LIMITACAO_TEMPORAL and m.limitacao_temporal_anos:
                doc.add_paragraph(
                    f"O valor será devido até {m.limitacao_temporal_anos} anos de tramitação "
                    f"sob o patrocínio do C&F."
                )
 
            if m.faixas_preco:
                table = doc.add_table(rows=1, cols=2)
                self._apply_table_grid(table)
                hdr = table.rows[0].cells
                hdr[0].text = "Faixa"
                hdr[1].text = "Valor"
                for faixa in m.faixas_preco:
                    row = table.add_row().cells
                    row[0].text = faixa.get("faixa", "")
                    row[1].text = faixa.get("valor", "")
 
            doc.add_paragraph(
                f"Entende-se por ativo aquele {tipo_label} que não foi definitivamente "
                f"extinto, baixado e arquivado no sistema do Tribunal ou respectivo órgão.",
                style="List Bullet",
            )
 
    def _add_exito(self, doc: Document, ex: "Exito") -> None:
        doc.add_heading("ÊXITO", level=3)
        doc.add_paragraph("Em relação ao honorário de êxito, será observado o seguinte:")
 
        if ex.subtipo == SubtipoExito.PERCENTUAL_FIXO and ex.percentual:
            doc.add_paragraph(
                f"O percentual de êxito será de {self._format_percentual(ex.percentual)} sobre {ex.base_calculo}."
            )
        elif ex.subtipo == SubtipoExito.PERCENTUAL_VARIAVEL and ex.faixas_percentual:
            doc.add_paragraph("O percentual será calculado conforme o valor do Benefício:")
            table = doc.add_table(rows=1, cols=2)
            self._apply_table_grid(table)
            hdr = table.rows[0].cells
            hdr[0].text = "Faixa de Valor"
            hdr[1].text = "Percentual"
            for faixa in ex.faixas_percentual:
                row = table.add_row().cells
                row[0].text = faixa.get("faixa", "")
                row[1].text = faixa.get("percentual", "")
 
        doc.add_paragraph(
            f"Incidência: {self._label_from_map(ex.incidencia, INCIDENCIA_EXITO_LABELS)}.",
            style="List Bullet",
        )
 
        doc.add_paragraph(
            "O percentual incidirá sobre o benefício econômico e/ou financeiro e/ou fiscal "
            "e/ou tributário, corrigido monetariamente, aproveitável à CONTRATANTE (Benefício), "
            "ainda que parcial.",
            style="List Bullet",
        )
 
        doc.add_paragraph(
            f"Forma de pagamento: {self._label_from_map(ex.forma_pagamento, FORMA_PAGAMENTO_LABELS)}.",
            style="List Bullet",
        )

        if ex.vencimento:
            doc.add_paragraph(
                f"Vencimento: {self._format_vencimento(ex.vencimento)}.",
                style="List Bullet",
            )
 
        if ex.tem_beneficio_prospectivo and ex.periodo_prospectivo_meses:
            doc.add_paragraph(
                f"Nos casos em que os serviços do C&F também proporcionarem Benefício prospectivo "
                f"à CONTRATANTE, incidirão honorários de êxito calculados sobre o período de "
                f"{ex.periodo_prospectivo_meses} meses.",
                style="List Bullet",
            )
 
        if ex.deduz_outro_honorario and ex.honorario_deduzido:
            doc.add_paragraph(
                f"O honorário de êxito será pago abatendo-se o valor pago a título de "
                f"{self._label_from_map(ex.honorario_deduzido, HONORARIO_LABELS)}.",
                style="List Bullet",
            )
 
    def _add_permuta(self, doc: Document, perm: "Permuta") -> None:
        doc.add_heading("PERMUTA", level=3)
        doc.add_paragraph(
            f"O serviço contratado será permutado com o serviço de {perm.objeto_permuta} "
            f"a ser prestado pela CONTRATANTE ao C&F. {perm.descricao}"
        )
        if perm.tem_torna and perm.valor_torna:
            doc.add_paragraph(
                f"A torna será de {valor_com_extenso(perm.valor_torna)}, "
                f"paga da seguinte forma: {perm.forma_pagamento_torna or 'a definir'}."
            )
 
    def _add_common_clauses(self, doc: Document) -> None:
        doc.add_heading("4. CLÁUSULAS COMUNS AOS HONORÁRIOS", level=2)
        clauses = [
            "Todos os valores previstos nesta contratação serão reajustados anualmente "
            "pela variação positiva e acumulada do IPCA, ou outro índice que vier a "
            "substitui-lo, sempre desde a data da assinatura do Contrato.",
            "Todo e qualquer pagamento devido ao C&F será feito por meio de boleto bancário "
            "ou transferência bancária para a conta de sua titularidade: Banco Inter - "
            "Ag. 0001 c/c 17841983-4 ou Pix 25463159000173.",
            "A CONTRATANTE se declara ciente das notórias tentativas gerais de fraude e "
            "golpes simulando contatos de advogados e escritórios de advocacia.",
            "A CONTRATANTE reconhece que qualquer pagamento realizado em inobservância ao "
            "previsto neste Contrato será considerado inválido e ineficaz.",
            "As obrigações de pagamento previstas neste Contrato serão devidas, independentemente "
            "de notificação, tão logo se dê o seu vencimento.",
            "O atraso no pagamento implicará na incidência do seguinte: juros de 1% a.m.; "
            "multa de 10% (dez por cento) sobre o valor em atraso e atualização monetária "
            "pelo IPCA, sem prejuízo de suspensão do serviço.",
        ]
        for clause in clauses:
            doc.add_paragraph(clause, style="List Bullet")
 
    def _add_accessories(self, doc: Document, ac: Acessorios) -> None:
        doc.add_heading("5. REEMBOLSOS, DESPESAS E OUTRAS VERBAS", level=2)
        if ac.tem_reembolso:
            doc.add_paragraph(
                "5.1. Valores adiantados pelo C&F serão reembolsados pela CONTRATANTE, "
                "mediante comprovação, no prazo de até 05 dias após a apresentação do(s) "
                "comprovante(s)."
            )
            if ac.reembolso_limitado and ac.descricao_limitacao_reembolso:
                doc.add_paragraph(
                    f"Limitação: {ac.descricao_limitacao_reembolso}"
                )
        doc.add_paragraph(
            "5.2. Custas, despesas, taxas, emolumentos, cópias xerográficas, diligências, "
            "correspondentes, peritos, assistentes técnicos, tradutores, serviços de entrega "
            "e correio, deslocamentos, transporte, alimentação e hospedagem serão suportados "
            "pela CONTRATANTE."
        )
 
    def _add_obligations(self, doc: Document) -> None:
        doc.add_heading("7. OBRIGAÇÕES DAS PARTES", level=2)
        doc.add_paragraph(
            "7.1. Obrigações da CONTRATANTE: (i) fornecer informações/documentos de forma "
            "completa e em tempo hábil; (ii) manter dados cadastrais atualizados; "
            "(iii) efetuar pagamentos dentro dos respectivos prazos."
        )
        doc.add_paragraph(
            "7.2. Obrigações do C&F: (i) executar o serviço com diligência, técnica e zelo; "
            "(ii) manter confidencialidade e sigilo profissional; (iii) fornecer informações/"
            "documentos relativas à prestação de serviço."
        )
        doc.add_paragraph(
            "A prestação de serviço advocatício constitui obrigação de meio, inexistindo "
            "obrigação de êxito e/ou resultado."
        )
 
    def _add_integrity(self, doc: Document) -> None:
        doc.add_heading("11. INTEGRIDADE E OUTROS", level=2)
        doc.add_paragraph(
            "As Partes comprometem-se a observar a legislação aplicável, incluindo Lei "
            "Anticorrupção e outras normas similares."
        )
        doc.add_paragraph(
            "As Partes comprometem-se a tratar dados pessoais estritamente para as "
            "finalidades deste Contrato, observando medidas razoáveis de segurança."
        )
        doc.add_paragraph(
            "A CONTRATANTE declara estar ciente de que o C&F, sob supervisão humana, "
            "utiliza ferramentas de inteligência artificial e outras tecnologias como "
            "apoio à prestação do serviço."
        )
 
    def _add_term_and_termination(self, doc: Document) -> None:
        doc.add_heading("12. PRAZO, RESCISÃO E OUTROS EFEITOS", level=2)
        doc.add_paragraph(
            "Ressalvada a hipótese de prazo específico pactuado entre as Partes, o "
            "presente Contrato é celebrado por tempo indeterminado, até que seja "
            "esgotado o objeto contratado."
        )
        doc.add_paragraph(
            "12.1. Qualquer Parte poderá rescindir este Contrato imotivadamente mediante "
            "notificação por escrito com antecedência mínima de 30 (trinta) dias."
        )
 
    def _add_ip(self, doc: Document) -> None:
        doc.add_heading("13. PROPRIEDADE INTELECTUAL", level=2)
        doc.add_paragraph(
            "13.1. A produção intelectual (teses, estratégias, modelos, documentos, "
            "minutas e know-how) desenvolvida pelo C&F permanece de sua titularidade."
        )
 
    def _add_general(self, doc: Document) -> None:
        doc.add_heading("14. DISPOSIÇÕES GERAIS", level=2)
        doc.add_paragraph(
            "Será considerada entregue a notificação e/ou comunicação encaminhada ao "
            "endereço declinado no preâmbulo deste Contrato."
        )
        doc.add_paragraph(
            "O presente contrato é título executivo extrajudicial, podendo ser utilizado "
            "para a execução judicial de quaisquer obrigações nele constantes."
        )
 
        doc.add_heading("15. FORO", level=2)
        doc.add_paragraph(
            "15.1. Fica eleito o foro da Comarca de Belo Horizonte/MG para dirimir "
            "quaisquer dúvidas ou controvérsias decorrentes deste Contrato."
        )
 
    def _add_signatures(self, doc: Document, data: ContratoRequest) -> None:
        doc.add_paragraph()
        doc.add_paragraph(
            f"Belo Horizonte, {self._format_date_pt_br(datetime.now())}."
        )
        doc.add_paragraph()
        doc.add_paragraph("_" * 50)
        doc.add_paragraph("CONTRATADO: CARVALHO & FURTADO ADVOGADOS")
        doc.add_paragraph()
 
        for i, contratante in enumerate(data.contratantes, 1):
            doc.add_paragraph("_" * 50)
            if isinstance(contratante, ContratantePJ):
                doc.add_paragraph(f"CONTRATANTE {i}: {contratante.razao_social}")
            elif isinstance(contratante, ContratantePF):
                doc.add_paragraph(f"CONTRATANTE {i}: {contratante.nome}")
            doc.add_paragraph()
 
        doc.add_paragraph()
        doc.add_paragraph("TESTEMUNHAS:")
        doc.add_paragraph()
        doc.add_paragraph("_" * 50)
        doc.add_paragraph("Nome:")
        doc.add_paragraph("CPF:")
        doc.add_paragraph()
        doc.add_paragraph("_" * 50)
        doc.add_paragraph("Nome:")
        doc.add_paragraph("CPF:")
 
    def _escopo_description(self, escopo: EscopoItem) -> str:
        if escopo.tipo == TipoEscopo.OUTRO and escopo.descricao_custom:
            return escopo.descricao_custom
 
        label = ESCOPO_LABELS.get(escopo.tipo, str(escopo.tipo))
 
        extras = []
        if escopo.descricao_custom:
            extras.append(escopo.descricao_custom)
        if escopo.numero_autos:
            extras.append(f"nos autos {escopo.numero_autos}")
        if escopo.demandas:
            extras.append(f"para ajuizamento: {escopo.demandas}")
        if escopo.pessoas_patrimonios:
            extras.append(f"pessoas/patrimonios: {escopo.pessoas_patrimonios}")
        if escopo.tipo_reestruturacao:
            extras.append(f"tipo: {escopo.tipo_reestruturacao}")
        if escopo.documentos:
            extras.append(f"documentos: {escopo.documentos}")
        if escopo.consulta:
            extras.append(f"consulta: {escopo.consulta}")
 
        if extras:
            label += " - " + "; ".join(extras)
 
        return label
 
    def _preco_resumo(self, escopo: EscopoItem) -> str:
        parts = []
        for tipo in escopo.honorarios:
            if tipo == TipoHonorario.HORA_TRABALHADA and escopo.hora_trabalhada:
                parts.append(f"{valor_com_extenso(escopo.hora_trabalhada.valor_hora)} por hora trabalhada")
            elif tipo == TipoHonorario.PRO_LABORE and escopo.pro_labore:
                parts.append(f"{valor_com_extenso(escopo.pro_labore.valor_total)} pro-labore")
            elif tipo == TipoHonorario.MENSALIDADE and escopo.mensalidade:
                parts.append(f"{valor_com_extenso(escopo.mensalidade.valor)} de mensalidade")
            elif tipo == TipoHonorario.EXITO and escopo.exito and escopo.exito.percentual:
                parts.append(f"{escopo.exito.percentual}% de exito")
            elif tipo == TipoHonorario.PERMUTA and escopo.permuta:
                parts.append(f"Permuta: {escopo.permuta.objeto_permuta}")
        return " + ".join(parts) if parts else "A definir"
