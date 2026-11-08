"""Previa HTML do contrato: o DOCX do gerador vira HTML, com o que foi digitado marcado.

Modulo de servico, sem HTTP. As rotas (routers/contract.py, documentos.py) so decidem
permissao e devolvem o resultado; os demais routers nao importam mais regra de previa do router.
`gerador` e' quem monta o DOCX (ContractGenerator ou ConsumidorGenerator): a previa nunca grava
arquivo (o DOCX vai para a memoria) nem usa o disco do contrato.
"""
from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from app.models.contract import Acessorios, ContratoRequest, EscopoItem
from app.services import contract_reviewer

logger = logging.getLogger(__name__)

# DocuSeal merge-tag (ex.: "{{Assinatura Fulano;type=signature;role=Contratante}}").
# No preview trocamos por uma linha de assinatura para nao vazar a sintaxe crua.
_SIG_TAG = re.compile(r"\{\{[^}]*?type=signature[^}]*?\}\}")

def _clean_preview_text(text: str) -> str:
    # A tag do DocuSeal e' invisivel no Word (texto branco) e o documento ja traz
    # a linha de assinatura; deixa-la virar underscores duplicava a linha na previa.
    return _SIG_TAG.sub("", text)


def _clause_level(paragraph_el) -> int | None:
    """Nível do parágrafo na lista de cláusulas, ou None se não for numerado."""
    from docx.oxml.ns import qn

    num_pr = paragraph_el.find(qn("w:pPr") + "/" + qn("w:numPr"))
    if num_pr is None:
        return None
    ilvl = num_pr.find(qn("w:ilvl"))
    return int(ilvl.get(qn("w:val"))) if ilvl is not None else 0


def _inline_html(paragraph) -> str:
    """Preserva negrito dos runs (nomes e CONTRATANTE/CONTRATADA na qualificacao)."""
    from html import escape

    if not paragraph.runs:
        return escape(_clean_preview_text(paragraph.text))
    bits: list[str] = []
    for run in paragraph.runs:
        piece = escape(_clean_preview_text(run.text or ""))
        if not piece:
            continue
        bits.append(f"<strong>{piece}</strong>" if run.bold else piece)
    return "".join(bits) or escape(_clean_preview_text(paragraph.text))


def docx_para_html(origem, ajustados: frozenset[str] = frozenset()) -> str:
    """Render the generated DOCX as simple HTML for inline preview (no external deps).
    Paragrafos cujo texto esta em `ajustados` (editados na etapa 7) saem com class="ajustado"."""
    from html import escape

    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(origem) if isinstance(origem, Path) else origem)
    parts: list[str] = []
    contadores = [0, 0, 0]  # niveis da lista de clausulas (o Word numera no .docx)
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, doc)
            text = _inline_html(p)
            if not text.strip():
                continue
            ilvl = _clause_level(child)
            if ilvl is not None:
                contadores[ilvl] += 1
                for abaixo in range(ilvl + 1, len(contadores)):
                    contadores[abaixo] = 0
                text = ".".join(str(n) for n in contadores[: ilvl + 1]) + ". " + text
            style = p.style.name if p.style else ""
            if style == "Heading 1":
                parts.append(f"<h1>{text}</h1>")
            elif style.startswith("Heading"):
                parts.append(f"<h3>{text}</h3>")
            elif p.text.strip() in ajustados:
                parts.append(f'<p class="ajustado">{text}</p>')
            else:
                parts.append(f"<p>{text}</p>")
        elif child.tag == qn("w:tbl"):
            t = Table(child, doc)
            has_borders = t._tbl.tblPr.first_child_found_in("w:tblBorders") is not None
            # <th> so' na linha marcada como cabecalho (w:tblHeader). A tabela do
            # milheiro nao tem titulo: a 1a linha ja e' dado.
            def _e_cabecalho(row) -> bool:
                trPr = row._tr.trPr
                return trPr is not None and trPr.find(qn("w:tblHeader")) is not None

            def celula_html(cell) -> str:
                # Cada paragrafo da celula e' uma linha. `cell.text` junta tudo num
                # texto so e o HTML colapsa a quebra: o rotulo da assinatura acabava
                # na mesma linha dos underscores.
                linhas = [
                    escape(_clean_preview_text(p.text)).strip() for p in cell.paragraphs
                ]
                return "<br>".join(linha for linha in linhas if linha)

            rows_html = "".join(
                "<tr>" + "".join(
                    f"<{'th' if _e_cabecalho(row) else 'td'}>{celula_html(c)}"
                    f"</{'th' if _e_cabecalho(row) else 'td'}>"
                    for c in row.cells
                ) + "</tr>"
                for row in t.rows
            )
            css = "" if has_borders else ' class="noborder"'
            parts.append(f"<table{css}>{rows_html}</table>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>"
        "body{font-family:'Segoe UI',sans-serif;max-width:800px;margin:2rem auto;"
        "font-size:.9rem;line-height:1.5;color:#000;background:#fff;padding:0 1rem}"
        "h1{text-align:center;font-size:1.1rem}"
        "h3{font-size:1rem;margin-top:1.2rem}"
        "p{text-align:justify}"
        "p.ajustado{background:#fef3c7;border-left:3px solid #d97706;padding:2px 6px}"
        "table{border-collapse:collapse;width:100%;margin:.5rem 0}"
        "td,th{border:1px solid #000;padding:6px}"
        "th{text-align:center}"
        "table.noborder td{border:none}"
        "</style></head>"
        f"<body>{''.join(parts)}</body></html>"
    )


def html_do_documento(doc, ajustados: frozenset[str] = frozenset()) -> str:
    """HTML de um Document do python-docx ainda na memoria (sem arquivo temporario)."""
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return docx_para_html(buf, ajustados)


# Contratante ficticio: na etapa 3 o cliente costuma estar pela metade e a
# previa de honorarios nao depende dele.
_CONTRATANTE_PREVIA = {
    "tipo": "PF", "nome": "Prévia", "nacionalidade": "brasileiro(a)", "cpf": "00000000000",
    "profissao": "-", "estado_civil": "Solteiro(a)", "endereco": "-", "email": "previa@cf.adv.br",
}


class PreviaHonorariosRequest(BaseModel):
    escopos: list[EscopoItem]
    acessorios: Optional[Acessorios] = None
    # True pede tambem a revisao de portugues da IA (lenta; o pop-up faz 2 chamadas).
    revisar: bool = False


_MARCA_DIGITADO = "background:rgba(250,204,21,.35);border-radius:2px;padding:0 1px"
_MARCA_RISCADO = "background:rgba(239,68,68,.18);color:#b91c1c;text-decoration:line-through"
_MARCA_IA = "background:rgba(34,197,94,.22);text-decoration:none;border-radius:2px;padding:0 1px"


def _padrao_do_texto(digitado: str):
    """Regex que acha no html o texto digitado, mesmo escrito um pouco diferente no
    contrato: inicial maiuscula/minuscula, espacos repetidos, aspas, ponto final.
    Com fronteira de palavra nas pontas ("sim" nao casa em "Assim") e fora de tags.
    Unica busca, usada para achar e para marcar. None se nao ha o que procurar."""
    from html import escape

    miolo = (digitado or "").strip().rstrip(".;, ").strip()
    if not miolo:
        return None
    partes: list[str] = []
    primeira = True
    for pedaco in re.split(r"(\s+)", miolo):
        if not pedaco:
            continue
        if pedaco.isspace():
            partes.append(r"\s+")
            continue
        for c in pedaco:
            if c in "\"'":
                partes.append("(?:" + "|".join(re.escape(x) for x in (c, escape(c), escape(c, quote=False), "&#39;")) + ")")
            elif primeira and c.isalpha():
                partes.append("[" + re.escape(c.lower()) + re.escape(c.upper()) + "]")
            else:
                partes.append(re.escape(escape(c)))
            primeira = False
    return re.compile(r"(?<!\w)" + "".join(partes) + r"(?!\w)(?![^<]*>)"), miolo


def _achar_no_html(html: str, digitado: str, destaque: bool = True) -> str | None:
    """Trecho do html que corresponde ao texto digitado, como esta no contrato (sem
    escape), ou None. Com destaque=True, texto curto (<12) ou so' numero/percentual
    ("10%") so' vale se tiver uma unica ocorrencia: melhor sem destaque que no lugar
    errado. destaque=False so' diz se o campo foi escrito no contrato (vai a IA)."""
    from html import unescape

    padrao = _padrao_do_texto(digitado)
    if not padrao:
        return None
    regex, miolo = padrao
    achados = [m.group(0) for m in regex.finditer(html)]
    if not achados:
        return None
    if destaque and (len(miolo) < 12 or not re.search(r"[^\W\d_]", miolo)) and len(achados) != 1:
        return None
    return unescape(achados[0])


def _marcar_digitados(html: str, textos: list, achados: list[dict]) -> str:
    """Amarelo = o que a pessoa digitou. Onde a IA propoe outro texto, o digitado sai
    riscado e a sugestao logo depois, em verde (o que o contrato recebe se aplicar).
    O mesmo texto digitado em mais de um honorario e' destacado em cada ocorrencia."""
    from html import escape

    # Cada trecho vira um intervalo; o mais longo vence quando dois se sobrepoem
    # (nada de <mark> dentro de <mark>), e o texto curto nunca cai dentro de tag.
    # Um item e' o texto ou (texto, trechos do html onde o gerador o escreveu): fora
    # desses trechos nunca marca. Cada item usa uma ocorrencia (texto igual em dois
    # honorarios = dois itens = duas marcas).
    itens = [(t, None) if isinstance(t, str) else t for t in textos]
    escolhidos: list[tuple[int, int, str]] = []
    for texto, spans in sorted(itens, key=lambda it: -len(it[0])):
        alvo = escape(texto)
        dentro = alvo
        for a in achados:
            bruto = (a.get("trecho") or "").strip()
            # a IA ve o texto como digitado; o contrato pode ter descido a inicial
            trecho = next((escape(t) for t in (bruto, bruto[:1].swapcase() + bruto[1:]) if t and escape(t) in dentro), "")
            if trecho:
                # ponytail: casa por substring; trecho dentro de sugestao ja inserida
                # nao e' tratado (o revisor ja descarta trechos aninhados).
                dentro = dentro.replace(
                    trecho,
                    f'<del style="{_MARCA_RISCADO}">{trecho}</del>'
                    f'<ins style="{_MARCA_IA}">{escape(a.get("sugestao") or "")}</ins>',
                    1,
                )
        marcado = f'<mark style="{_MARCA_DIGITADO}">{dentro}</mark>'
        regex = _padrao_do_texto(texto)[0]
        for m in regex.finditer(html):
            if spans is not None and not any(i0 <= m.start() and m.end() <= f for i0, f in spans):
                continue
            if any(m.start() < f and i0 < m.end() for i0, f, _ in escolhidos):
                continue
            escolhidos.append((m.start(), m.end(), marcado))
            break
    for ini, fim, marcado in sorted(escolhidos, reverse=True):
        html = html[:ini] + marcado + html[fim:]
    return html


_BLOCO = re.compile(r"<(?:p|h1|h3|table)(?=[\s>])")


def _blocos(html: str) -> list[tuple[int, int]]:
    """Intervalos (inicio, fim) dos paragrafos/titulos/tabelas do html do contrato."""
    ini = [m.start() for m in _BLOCO.finditer(html)]
    return list(zip(ini, ini[1:] + [len(html)]))


def _html_honorarios(escopos: list, acessorios, gerador) -> str:
    data = ContratoRequest.model_validate(
        {
            "contratantes": [_CONTRATANTE_PREVIA],
            "escopos": escopos,
            "acessorios": acessorios or Acessorios(),
            "participacao": {"tem_participacao": False},
        },
        context={"previa": True},  # pop-up com formulario pela metade
    )
    html = html_do_documento(gerador._build_document(data))
    # Secoes saem como <h3> numerado; recorta da secao 3 ate a seguinte.
    inicio = html.rfind("<h3>", 0, html.find("OUTRAS DISPOSIÇÕES SOBRE HONORÁRIOS"))
    fim = html.rfind("<h3>", 0, html.find("CLÁUSULAS GERAIS"))
    return html[inicio:fim]


def _tirar_texto(obj, texto: str):
    """Copia do dump com todo valor igual a `texto` esvaziado."""
    if isinstance(obj, dict):
        return {k: _tirar_texto(v, texto) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_tirar_texto(v, texto) for v in obj]
    return "" if obj == texto else obj


def _trechos_do_campo(html: str, body: "PreviaHonorariosRequest", texto: str, gerador) -> list[tuple[int, int]] | None:
    """Onde o gerador escreveu o campo: gera o contrato de novo sem o texto e fica com
    os blocos que sumiram ou mudaram. Falhou = None (sem destaque, nunca no lugar errado;
    o campo continua indo a IA)."""
    from collections import Counter

    try:
        sem = body.model_dump(mode="json")
        sem = PreviaHonorariosRequest(**_tirar_texto(sem, texto))
        html_sem = _html_honorarios(sem.escopos, sem.acessorios, gerador)
    except Exception:
        logger.warning("Previa: nao foi possivel localizar o campo no contrato", exc_info=True)
        return None
    restam = Counter(html_sem[i:f] for i, f in _blocos(html_sem))
    spans = []
    for i, f in _blocos(html):
        if restam[html[i:f]] > 0:
            restam[html[i:f]] -= 1
        else:
            spans.append((i, f))
    return spans


def previa_honorarios(body: PreviaHonorariosRequest, gerador) -> dict:
    """Previa so' da secao de honorarios, para o pop-up do wizard: o texto digitado
    vem destacado e, com revisar=True, a correcao da IA aparece no lugar. Nada e' gravado."""
    from app.utils.currency import percentual_com_extenso

    html = _html_honorarios(body.escopos, body.acessorios, gerador)

    dump = {"escopos": [e.model_dump(mode="json") for e in body.escopos]}
    # O gerador tira a pontuacao final do que foi digitado; o destaque tem de casar.
    completos = contract_reviewer.campos_abertos(dump)
    # O contrato pode escrever o texto diferente do digitado (inicial, ponto final,
    # espacos); a busca no html e o destaque usam o texto como saiu no contrato.
    # Cada campo so' vale dentro dos blocos onde o gerador o escreveu.
    trechos: dict = {}
    como_sai = []
    for c in completos:
        if c[1] not in trechos:
            trechos[c[1]] = _trechos_do_campo(html, body, c[1], gerador)
        sp = trechos[c[1]]
        if sp is None:
            # nao deu para localizar: o campo vai a IA (procurado no html todo), sem destaque
            como_sai.append((c, _achar_no_html(html, c[1], destaque=False), None, []))
            continue
        regiao = "".join(html[i:f] for i, f in sp)
        como_sai.append((c, _achar_no_html(regiao, c[1], destaque=False), _achar_no_html(regiao, c[1]), sp))
    # Vai a IA o que foi escrito no contrato; so' recebe destaque o que se acha sem duvida.
    completos = [c for c, escrito, _, _ in como_sai if escrito and len(escrito) >= 3]
    textos: list = [(achado, sp) for _, _, achado, sp in como_sai if achado and len(achado) >= 3]
    # Desconto percentual nao e' texto livre, mas e' a "especificacao" que a pessoa preencheu.
    for h in (e.model_dump(mode="json").get(k) or {} for e in body.escopos for k in contract_reviewer.HONORARIO_ROTULOS):
        if h.get("tem_desconto") and h.get("desconto_tipo") != "livre" and h.get("desconto_percentual"):
            textos.append(percentual_com_extenso(h["desconto_percentual"]))

    findings: list[dict] = []
    avisos: list[dict] = []
    erro = None
    if body.revisar and completos and not contract_reviewer.is_configured():
        # Sem isto o pop-up dizia "nenhuma correção necessária" sem a IA ter olhado nada.
        erro = "Revisão da IA não configurada neste ambiente (DEEPSEEK_API_KEY)."
    elif body.revisar and completos:
        try:
            # Cada campo vai com a frase fixa do contrato em volta (so' contexto: a
            # correcao tem de cair dentro do que foi digitado — so_do_digitado garante).
            achados = contract_reviewer.so_do_digitado(
                contract_reviewer.review_text(
                    contract_reviewer.texto_para_revisao(completos), avisar_ambiguidade=True
                ),
                dump,
            )
            findings = [f for f in achados if f.get("tipo") != "aviso"]
            avisos = [f for f in achados if f.get("tipo") == "aviso"]
        except contract_reviewer.ContractReviewError as e:
            logger.warning("Revisao da previa de honorarios indisponivel: %s", e)
            erro = "Revisão da IA indisponível."
    return {
        "html": _marcar_digitados(html, textos, findings),
        "findings": findings,
        "avisos": avisos,
        "erro": erro,
    }


def previa_com_itens(data: ContratoRequest, gerador) -> dict:
    """Previa em HTML + a lista de clausulas (id, texto atual/padrao, ajuste) para o painel 'Ajustar texto'."""
    doc = gerador._build_document(data)
    ctx = doc._cf_itens
    html = html_do_documento(doc, frozenset(i["texto"] for i in ctx.itens if i["ajustado"]))
    return {"preview_html": html, "itens": ctx.itens, "ajustes_descartados": ctx.descartados()}
