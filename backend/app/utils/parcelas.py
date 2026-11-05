from __future__ import annotations

from datetime import date
from decimal import ROUND_DOWN, Decimal


def dividir_parcelas(total: float, n: int) -> list[Decimal]:
    """Divide `total` em `n` parcelas em centavos; a última absorve a diferença.

    14000, 5 -> 5 x 2800,00 | 10000, 3 -> 3333,33; 3333,33; 3333,34.
    """
    if n < 1:
        raise ValueError("n deve ser >= 1")
    centavos = int((Decimal(str(total)) * 100).to_integral_value())
    base = int((Decimal(centavos) / n).to_integral_value(rounding=ROUND_DOWN))
    parcelas = [base] * n
    parcelas[-1] += centavos - base * n
    return [Decimal(c) / 100 for c in parcelas]


def data_iso(valor: str | None) -> date | None:
    try:
        return date.fromisoformat((valor or "")[:10])
    except ValueError:
        return None
