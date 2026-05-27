from decimal import Decimal

import pytest

from app.services.pagamento_calculator import calcular_componentes_pagamento


def test_calcula_imposto_e_liquido():
    out = calcular_componentes_pagamento(
        valor_bruto=10000.0,
        aliquota_total=0.1545,
        percentual_captacao=10.0,
        percentual_performance=0.0,
        discriminado=True,
        valor_contratual_informado=None,
    )
    assert out["imposto_total"] == 1545.00
    assert out["valor_liquido"] == 8455.00
    assert out["valor_contratual"] == 8455.00
    assert out["valor_participacao"] == 845.50


def test_split_5050_quando_nao_discriminado():
    out = calcular_componentes_pagamento(
        valor_bruto=10000.0,
        aliquota_total=0.1545,
        percentual_captacao=10.0,
        percentual_performance=10.0,
        discriminado=False,
        valor_contratual_informado=None,
    )
    assert out["valor_contratual"] == 4227.50
    assert out["valor_participacao"] == 845.50


def test_aliquota_zero():
    out = calcular_componentes_pagamento(
        valor_bruto=1000.0,
        aliquota_total=0.0,
        percentual_captacao=20.0,
        percentual_performance=0.0,
        discriminado=True,
        valor_contratual_informado=None,
    )
    assert out["imposto_total"] == 0.0
    assert out["valor_liquido"] == 1000.0
    assert out["valor_participacao"] == 200.0


def test_valor_contratual_informado_override():
    out = calcular_componentes_pagamento(
        valor_bruto=10000.0,
        aliquota_total=0.1545,
        percentual_captacao=10.0,
        percentual_performance=0.0,
        discriminado=True,
        valor_contratual_informado=5000.0,
    )
    assert out["valor_contratual"] == 5000.0
    assert out["valor_participacao"] == 500.0


def test_valor_bruto_negativo_raises():
    with pytest.raises(ValueError):
        calcular_componentes_pagamento(
            valor_bruto=-100.0, aliquota_total=0.1545, percentual_captacao=0,
            percentual_performance=0, discriminado=True, valor_contratual_informado=None,
        )


def test_aliquota_acima_de_um_raises():
    with pytest.raises(ValueError):
        calcular_componentes_pagamento(
            valor_bruto=1000.0, aliquota_total=1.1, percentual_captacao=0,
            percentual_performance=0, discriminado=True, valor_contratual_informado=None,
        )
