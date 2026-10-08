"""Parser de NFS-e ABRASF (variante BHISS). Usa defusedxml para mitigar XXE."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import ParseError, fromstring
from defusedxml.common import DefusedXmlException

from app.utils.documento import normalizar_doc


class NFSeParseError(Exception):
    pass


_NS = {"a": "http://www.abrasf.org.br/nfse.xsd"}


def _digits(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\D", "", s)


def _find(elem: Element | None, path: str) -> Element | None:
    if elem is None:
        return None
    found = elem.find(path, _NS)
    if found is not None:
        return found
    return elem.find(re.sub(r"a:", "", path))


def _txt(elem: Element | None, path: str) -> str | None:
    found = _find(elem, path)
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _decimal(s: str | None) -> Decimal:
    if not s:
        return Decimal("0")
    return Decimal(s)


def parse_nfse_xml(xml: bytes) -> "NFSeData":
    from app.models.nfse import NFSeData

    try:
        root = fromstring(xml)
    except (ParseError, DefusedXmlException, Exception) as e:
        raise NFSeParseError(f"XML invalido: {e}") from e

    inf = _find(root, ".//a:InfNfse")
    if inf is None:
        raise NFSeParseError("InfNfse nao encontrado")

    numero = _txt(inf, "a:Numero")
    if not numero:
        raise NFSeParseError("Numero ausente")

    codigo_ver = _txt(inf, "a:CodigoVerificacao")

    competencia_str = _txt(inf, "a:Competencia")
    data_emissao_str = _txt(inf, "a:DataEmissao")
    if not competencia_str or not data_emissao_str:
        raise NFSeParseError("Competencia/DataEmissao ausente")

    competencia = date.fromisoformat(competencia_str[:10])
    data_emissao = date.fromisoformat(data_emissao_str[:10])

    valores = _find(inf, "a:Servico/a:Valores")
    if valores is None:
        raise NFSeParseError("Servico/Valores ausente")

    valor_servicos = _decimal(_txt(valores, "a:ValorServicos"))
    iss_retido_flag = _txt(valores, "a:IssRetido") == "1"
    iss = _decimal(_txt(valores, "a:ValorIss")) if iss_retido_flag else Decimal("0")
    irrf = _decimal(_txt(valores, "a:ValorIr"))
    pis = _decimal(_txt(valores, "a:ValorPis"))
    cofins = _decimal(_txt(valores, "a:ValorCofins"))
    csll = _decimal(_txt(valores, "a:ValorCsll"))

    discriminacao = _txt(inf, "a:Servico/a:Discriminacao")

    cnpj_prest = _digits(_txt(inf, "a:PrestadorServico/a:IdentificacaoPrestador/a:Cnpj"))
    if len(cnpj_prest) != 14:
        raise NFSeParseError(f"CNPJ prestador invalido: {cnpj_prest!r}")

    tomador_cnpj = normalizar_doc(_txt(inf, "a:TomadorServico/a:IdentificacaoTomador/a:CpfCnpj/a:Cnpj"))
    tomador_cpf = _digits(_txt(inf, "a:TomadorServico/a:IdentificacaoTomador/a:CpfCnpj/a:Cpf"))
    tomador_doc = tomador_cnpj or tomador_cpf
    if not tomador_doc:
        raise NFSeParseError("Tomador sem CPF/CNPJ")
    tomador_nome = _txt(inf, "a:TomadorServico/a:RazaoSocial")

    canc = _find(root, ".//a:NfseCancelamento/a:Confirmacao/a:DataHora")
    cancelada = canc is not None and canc.text is not None
    data_cancelamento = None
    if cancelada:
        try:
            data_cancelamento = datetime.fromisoformat(canc.text.strip())
        except Exception:
            data_cancelamento = None

    return NFSeData(
        cnpj_prestador=cnpj_prest,
        numero=numero,
        serie=None,
        codigo_verificacao=codigo_ver,
        competencia=competencia,
        data_emissao=data_emissao,
        tomador_doc=tomador_doc,
        tomador_nome=tomador_nome,
        valor_servicos=valor_servicos,
        iss_retido=iss,
        irrf=irrf,
        pis=pis,
        cofins=cofins,
        csll=csll,
        discriminacao=discriminacao,
        cancelada=cancelada,
        data_cancelamento=data_cancelamento,
        xml_raw=xml,
    )


# --- Padrao Nacional (ADN) -------------------------------------------------
# Leiaute do XSD oficial v1.01 (http://www.sped.fazenda.gov.br/nfse).

_NS_NAC = "{http://www.sped.fazenda.gov.br/nfse}"

# tpRetPisCofins -> (PIS retido, COFINS retido). CSLL vem de vRetCSLL.
_RET_PIS_COFINS = {
    "1": (True, True), "3": (True, True), "4": (True, True),
    "5": (True, False), "6": (False, True), "7": (False, True), "9": (True, False),
}

# Eventos de cancelamento: e101101 (cancelamento) e e105102 (por substituicao).
_EVENTOS_CANCELAMENTO = ("e101101", "e105102")


def _n(elem: Element | None, path: str) -> str | None:
    """Texto do caminho no namespace nacional ('a/b' -> '{ns}a/{ns}b')."""
    if elem is None:
        return None
    found = elem.find("/".join(_NS_NAC + p for p in path.split("/")))
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _doc(elem: Element | None, path: str) -> str:
    return _digits(_n(elem, f"{path}/CNPJ") or _n(elem, f"{path}/CPF"))


def _parse_nfse_nacional(root: Element, xml: bytes, cnpj_consultado: str) -> "NFSeData":
    from app.models.nfse import NFSeData

    inf = root.find(f"{_NS_NAC}infNFSe")
    dps = inf.find(f"{_NS_NAC}DPS/{_NS_NAC}infDPS") if inf is not None else None
    if inf is None or dps is None:
        raise NFSeParseError("infNFSe/infDPS nao encontrado")

    chave = (inf.get("Id") or "").removeprefix("NFS")
    numero = _n(inf, "nNFSe")
    emitente = _doc(inf, "emit")
    competencia_str = _n(dps, "dCompet")
    emissao_str = _n(dps, "dhEmi")
    if not numero or len(chave) != 50:
        raise NFSeParseError("Numero/chave de acesso ausente")
    if len(emitente) not in (11, 14):
        raise NFSeParseError(f"Documento do emitente invalido: {emitente!r}")
    if not competencia_str or not emissao_str:
        raise NFSeParseError("dCompet/dhEmi ausente")

    tomador_doc = _doc(dps, "toma") or _digits(_n(dps, "toma/NIF"))[:14]
    direcao = "emitida" if emitente == cnpj_consultado else "recebida"
    if not tomador_doc:
        if direcao == "emitida":
            raise NFSeParseError("Tomador sem CPF/CNPJ")
        tomador_doc = cnpj_consultado  # nota recebida sem toma: o escritorio

    trib = dps.find(f"{_NS_NAC}valores/{_NS_NAC}trib")
    iss = _decimal(_n(inf, "valores/vISSQN")) if _n(trib, "tribMun/tpRetISSQN") in ("2", "3") else Decimal("0")
    pis_ret, cofins_ret = _RET_PIS_COFINS.get(_n(trib, "tribFed/piscofins/tpRetPisCofins") or "", (False, False))

    return NFSeData(
        cnpj_prestador=emitente,
        numero=numero,
        serie=None,
        codigo_verificacao=None,
        competencia=date.fromisoformat(competencia_str[:10]),
        data_emissao=date.fromisoformat(emissao_str[:10]),
        tomador_doc=tomador_doc,
        tomador_nome=_n(dps, "toma/xNome"),
        valor_servicos=_decimal(_n(dps, "valores/vServPrest/vServ")),
        iss_retido=iss,
        irrf=_decimal(_n(trib, "tribFed/vRetIRRF")),
        pis=_decimal(_n(trib, "tribFed/piscofins/vPis")) if pis_ret else Decimal("0"),
        cofins=_decimal(_n(trib, "tribFed/piscofins/vCofins")) if cofins_ret else Decimal("0"),
        csll=_decimal(_n(trib, "tribFed/vRetCSLL")),
        discriminacao=_n(dps, "serv/cServ/xDescServ"),
        xml_raw=xml,
        direcao=direcao,
        chave_acesso=chave,
    )


def _parse_evento_nacional(root: Element, xml: bytes) -> "CancelamentoData | None":
    from app.models.nfse import CancelamentoData

    ped = root.find(f"{_NS_NAC}infEvento/{_NS_NAC}pedRegEvento/{_NS_NAC}infPedReg")
    if ped is None:
        raise NFSeParseError("infPedReg nao encontrado")
    if not any(ped.find(_NS_NAC + e) is not None for e in _EVENTOS_CANCELAMENTO):
        return None  # outros eventos (manifestacao, bloqueio...) nao mudam a nota
    chave = _n(ped, "chNFSe")
    if not chave or len(chave) != 50:
        raise NFSeParseError("chNFSe ausente no evento")
    dh = _n(ped, "dhEvento")
    return CancelamentoData(
        chave_acesso=chave,
        data_cancelamento=datetime.fromisoformat(dh) if dh else None,
        xml_raw=xml,
    )


def parse_documento(xml: bytes, cnpj_consultado: str) -> "NFSeData | CancelamentoData | None":
    """Le um documento distribuido (ABRASF ou Padrao Nacional).

    Devolve NFSeData para nota, CancelamentoData para evento de cancelamento e
    None para evento que nao altera a nota."""
    try:
        root = fromstring(xml)
    except (ParseError, DefusedXmlException, Exception) as e:
        raise NFSeParseError(f"XML invalido: {e}") from e

    if root.tag == f"{_NS_NAC}NFSe":
        return _parse_nfse_nacional(root, xml, _digits(cnpj_consultado))
    if root.tag == f"{_NS_NAC}evento":
        return _parse_evento_nacional(root, xml)
    return parse_nfse_xml(xml)
