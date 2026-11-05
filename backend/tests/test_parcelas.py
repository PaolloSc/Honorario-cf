from decimal import Decimal

import pytest

from app.utils.parcelas import dividir_parcelas


def test_divisao_exata():
    assert dividir_parcelas(14000, 5) == [Decimal("2800")] * 5


def test_ultima_parcela_absorve_os_centavos():
    p = dividir_parcelas(10000, 3)
    assert p == [Decimal("3333.33"), Decimal("3333.33"), Decimal("3333.34")]
    assert sum(p) == Decimal("10000")


def test_soma_sempre_fecha_o_total():
    for total, n in [(1234.56, 7), (0.10, 3), (99999.99, 12), (1, 1)]:
        assert sum(dividir_parcelas(total, n)) == Decimal(str(total)).quantize(Decimal("0.01"))


def test_n_invalido():
    with pytest.raises(ValueError):
        dividir_parcelas(100, 0)
