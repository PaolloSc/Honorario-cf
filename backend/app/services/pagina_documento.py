"""Pagina e assinaturas dos documentos do escritorio que seguem o layout do CONTRATO.docx
(contrato de consumidor, aditivo, distrato e substabelecimento).

Peca de formatacao: margens, fonte, entrelinha, destaque em negrito das partes e a grade de
assinaturas com as tags do DocuSeal. Entra nos geradores como mixin plano, antes do
ContractGenerator, que fornece o template timbrado e o fluxo de montagem. Antes, os documentos
complementares herdavam do contrato de consumidor so' para ter isto (herança em cadeia de 4 niveis).
"""
from __future__ import annotations

import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


class PaginaCompacta:
    # ── Formatacao (medida no CONTRATO.docx do escritorio) ────────
    #
    # Segoe UI 11pt, justificado, entrelinha 1,15, sem espaco depois do
    # paragrafo (o original separa os blocos com linha em branco) e margens
    # 0,75 / 1,25 / 3 / 2 cm. Difere do contrato de honorarios, por isso
    # esta classe sobrescreve os tres metodos de layout.

    FONTE = "Segoe UI"
    TAMANHO = Pt(11)
    ENTRELINHA = 1.15
    # Uma linha em branco de 11pt a 1,15 ≈ 12pt: mesmo respiro do original.
    ESPACO_DEPOIS = Pt(12)

    def _apply_page_setup(self, doc) -> None:
        for section in doc.sections:
            section.top_margin = Cm(0.75)
            section.bottom_margin = Cm(1.25)
            section.left_margin = Cm(3)
            section.right_margin = Cm(2)

    def _apply_base_styles(self, doc) -> None:
        for style_name in ("Normal", "Body Text", "List Paragraph"):
            if style_name not in doc.styles:
                continue
            style = doc.styles[style_name]
            style.font.name = self.FONTE
            style._element.rPr.rFonts.set(qn("w:eastAsia"), self.FONTE)
            style.font.size = self.TAMANHO
            style.font.color.rgb = RGBColor(0, 0, 0)
            style.paragraph_format.line_spacing = self.ENTRELINHA
            style.paragraph_format.space_after = self.ESPACO_DEPOIS

    def _format_paragraph(self, paragraph, assinatura: bool = False, justify_body: bool = False) -> None:
        # justify_body e' um parametro da classe base (ContractGenerator) — aqui o
        # corpo ja e' sempre justificado (ver abaixo), entao so' aceita o argumento
        # pra manter a assinatura compativel com a chamada de _apply_document_standard.
        del justify_body
        is_heading = paragraph.style and paragraph.style.name.startswith("Heading")
        is_signature = self._is_signature_paragraph(paragraph.text) or assinatura

        paragraph.paragraph_format.line_spacing = self.ENTRELINHA
        paragraph.paragraph_format.space_after = (
            Pt(0) if is_signature else self.ESPACO_DEPOIS
        )
        paragraph.paragraph_format.keep_together = True
        if is_heading:
            paragraph.paragraph_format.keep_with_next = True
        if is_signature:
            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.CENTER if assinatura else WD_ALIGN_PARAGRAPH.LEFT
            )
        # Corpo justificado; titulo, assinaturas e celulas da grade nao.
        # Justificar texto curto na tabela de assinatura deforma o DocuSeal.
        parent = paragraph._element.getparent()
        in_table = parent is not None and parent.tag == qn("w:tc")
        if paragraph.alignment is None and not is_signature and not in_table:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        for run in paragraph.runs:
            run.font.name = self.FONTE
            run._element.rPr.rFonts.set(qn("w:eastAsia"), self.FONTE)
            run.font.size = self.TAMANHO
            run.font.color.rgb = RGBColor(0, 0, 0)

    @staticmethod
    def _alinhado_a_esquerda(paragraph):
        """Linhas curtas (contatos, dados bancarios) nao devem ser justificadas."""
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        return paragraph

    _PAPEL_NEGRITO = re.compile(r"(CONTRATANTES|CONTRATANTE|CONTRATADA)")

    def _paragrafo_com_destaques(self, doc: Document, texto: str, nomes: list[str]):
        """Qualificacao: negrito so nos nomes das partes e em CONTRATANTE/CONTRATADA."""
        p = doc.add_paragraph()
        nomes_ok = sorted({n for n in nomes if n}, key=len, reverse=True)
        if nomes_ok:
            padrao = "(" + "|".join(re.escape(n) for n in nomes_ok) + r"|CONTRATANTES|CONTRATANTE|CONTRATADA)"
            splitter = re.compile(padrao)
        else:
            splitter = self._PAPEL_NEGRITO

        pos = 0
        for m in splitter.finditer(texto):
            if m.start() > pos:
                p.add_run(texto[pos:m.start()]).bold = False
            p.add_run(m.group(0)).bold = True
            pos = m.end()
        if pos < len(texto):
            p.add_run(texto[pos:]).bold = False
        return p

    def _grid_assinaturas(self, doc: Document, entries: list[tuple[str, list[str]]]) -> None:
        """Assinaturas 2 por linha. Rotulo e' uma lista de linhas (nome / CPF / papel).

        Proprio deste contrato: nao mexe no grid do contrato de honorarios.
        """
        if not entries:
            return

        table = doc.add_table(rows=(len(entries) + 1) // 2, cols=2)
        table.autofit = True
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for idx, (tag, linhas) in enumerate(entries):
            cell = table.cell(idx // 2, idx % 2)
            cell.paragraphs[0].text = tag  # tag do DocuSeal
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            for linha in linhas:
                p = cell.add_paragraph(linha)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cell.add_paragraph()
