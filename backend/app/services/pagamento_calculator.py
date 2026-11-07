"""Calculo SAP-like: valor_bruto -> imposto -> liquido -> contratual -> participacao.

Replica formula da Planilha de Participacoes 2026, em Decimal (centavos, arredondamento
comercial: meio centavo sobe):
- F = E * aliquota_total          (imposto)
- G = E - F                       (liquido contratual)
- H = G * (cap% + perf%) / 100   (participacao)
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal("0.01")


def dinheiro(valor) -> Decimal:
    """Qualquer numero (float, int, str, Decimal) -> Decimal com 2 casas."""
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def calcular_componentes_pagamento(
    *,
    valor_bruto,
    aliquota_total,
    percentual_captacao,
    percentual_performance,
    discriminado: bool,
    valor_contratual_informado=None,
) -> dict[str, Decimal]:
    bruto = Decimal(str(valor_bruto))
    aliquota = Decimal(str(aliquota_total))
    if bruto < 0:
        raise ValueError(f"valor_bruto deve ser >= 0, recebido {valor_bruto}")
    if not (0 <= aliquota <= 1):
        raise ValueError(f"aliquota_total fora de [0,1]: {aliquota_total}")

    imposto_total = dinheiro(bruto * aliquota)
    valor_liquido = dinheiro(bruto - imposto_total)

    if discriminado:
        if valor_contratual_informado is not None:
            valor_contratual = dinheiro(valor_contratual_informado)
        else:
            valor_contratual = valor_liquido
    else:
        valor_contratual = dinheiro(valor_liquido / 2)

    pct_efetivo = Decimal(str(percentual_captacao or 0)) + Decimal(str(percentual_performance or 0))
    valor_participacao = dinheiro(valor_contratual * pct_efetivo / 100)

    return {
        "imposto_total": imposto_total,
        "valor_liquido": valor_liquido,
        "valor_contratual": valor_contratual,
        "valor_participacao": valor_participacao,
    }
