from datetime import date
from decimal import Decimal
import importlib
import importlib.util


def _nfse_data_cls():
    assert importlib.util.find_spec("app.models.nfse") is not None
    return importlib.import_module("app.models.nfse").NFSeData


def test_nfse_data_calculates_valor_liquido_from_taxes():
    nfse = _nfse_data_cls()(
        cnpj_prestador="12345678000199",
        numero="1",
        competencia=date(2026, 5, 1),
        data_emissao=date(2026, 5, 2),
        tomador_doc="98765432000100",
        valor_servicos=Decimal("1000.00"),
        iss_retido=Decimal("30.00"),
        irrf=Decimal("20.00"),
        pis=Decimal("5.00"),
        cofins=Decimal("10.00"),
        csll=Decimal("15.00"),
        xml_raw=b"x",
    )

    assert nfse.valor_liquido == Decimal("920.00")
