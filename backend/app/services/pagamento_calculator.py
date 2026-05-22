"""Calculo SAP-like: valor_bruto -> imposto -> liquido -> contratual -> participacao.

Replica formula da Planilha de Participacoes 2026:
- F = E * aliquota_total          (imposto)
- G = E - F                       (liquido contratual)
- H = G * (cap% + perf%) / 100   (participacao)
"""
from __future__ import annotations


def calcular_componentes_pagamento(
    *,
    valor_bruto: float,
    aliquota_total: float,
    percentual_captacao: float,
    percentual_performance: float,
    discriminado: bool,
    valor_contratual_informado: float | None,
) -> dict[str, float]:
    if valor_bruto < 0:
        raise ValueError(f"valor_bruto deve ser >= 0, recebido {valor_bruto}")
    if not (0 <= aliquota_total <= 1):
        raise ValueError(f"aliquota_total fora de [0,1]: {aliquota_total}")

    imposto_total = round(valor_bruto * aliquota_total, 2)
    valor_liquido = round(valor_bruto - imposto_total, 2)

    if discriminado:
        if valor_contratual_informado is not None:
            valor_contratual = round(valor_contratual_informado, 2)
        else:
            valor_contratual = valor_liquido
    else:
        valor_contratual = round(valor_liquido * 0.5, 2)

    pct_efetivo = (percentual_captacao or 0.0) + (percentual_performance or 0.0)
    valor_participacao = round(valor_contratual * pct_efetivo / 100, 2)

    return {
        "imposto_total": imposto_total,
        "valor_liquido": valor_liquido,
        "valor_contratual": valor_contratual,
        "valor_participacao": valor_participacao,
    }
