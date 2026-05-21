from decimal import Decimal
from pathlib import Path

import pytest

from app.services.nfse_parser import NFSeParseError, parse_nfse_xml


FIXTURES = Path(__file__).parent / "fixtures" / "nfse"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parse_minimo_pj_tomador():
    nf = parse_nfse_xml(_load("abrasf_minimo.xml"))
    assert nf.cnpj_prestador == "12345678000199"
    assert nf.numero == "1000"
    assert nf.codigo_verificacao == "ABC123"
    assert nf.tomador_doc == "98765432000100"
    assert nf.tomador_nome == "Cliente Exemplo LTDA"
    assert nf.valor_servicos == Decimal("1500.00")
    assert nf.iss_retido == Decimal("0")
    assert nf.cancelada is False
    assert "maio/2026" in (nf.discriminacao or "")


def test_parse_pf_tomador():
    nf = parse_nfse_xml(_load("abrasf_pf_tomador.xml"))
    assert nf.tomador_doc == "12345678901"
    assert "abc12345" in (nf.discriminacao or "").lower()


def test_parse_cancelada():
    nf = parse_nfse_xml(_load("abrasf_cancelada.xml"))
    assert nf.cancelada is True
    assert nf.data_cancelamento is not None


def test_parse_com_retencoes_federais():
    nf = parse_nfse_xml(_load("abrasf_com_retencoes.xml"))
    assert nf.valor_servicos == Decimal("10000.00")
    assert nf.iss_retido == Decimal("500.00")
    assert nf.pis == Decimal("65.00")
    assert nf.cofins == Decimal("300.00")
    assert nf.irrf == Decimal("150.00")
    assert nf.csll == Decimal("100.00")
    assert nf.valor_liquido == Decimal("8885.00")


def test_parse_malformado_levanta():
    with pytest.raises(NFSeParseError):
        parse_nfse_xml(_load("abrasf_malformado.xml"))


def test_xxe_bloqueado():
    with pytest.raises(NFSeParseError):
        parse_nfse_xml(_load("xxe_attack.xml"))
