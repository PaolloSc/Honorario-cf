"""Parser de NFS-e ABRASF (variante BHISS). Usa defusedxml para mitigar XXE."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import ParseError, fromstring
from defusedxml.common import DefusedXmlException


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

    tomador_cnpj = _digits(_txt(inf, "a:TomadorServico/a:IdentificacaoTomador/a:CpfCnpj/a:Cnpj"))
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
