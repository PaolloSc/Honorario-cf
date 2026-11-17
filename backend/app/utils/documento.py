"""Normalização de CPF/CNPJ.

O CNPJ alfanumérico (Receita, a partir de jul/2026) tem letras A-Z maiúsculas nas
12 primeiras posições; tirar só os não-dígitos apagaria as letras. Contrato e NFSe
precisam passar pela MESMA normalização para o casamento por documento funcionar.
"""
from __future__ import annotations

import re

_NAO_ALFANUMERICO = re.compile(r"[^0-9A-Z]")


def normalizar_doc(valor: str | None) -> str:
    """'12.abc.345/01de-35' -> '12ABC34501DE35'; '123.456.789-09' -> '12345678909'."""
    if not valor:
        return ""
    return _NAO_ALFANUMERICO.sub("", valor.upper())


def cpf_valido(valor: str | None) -> bool:
    """11 dígitos com os dois verificadores certos (recusa 000.000.000-00 e afins)."""
    d = normalizar_doc(valor)
    if len(d) != 11 or not d.isdigit() or d == d[0] * 11:
        return False
    for n in (9, 10):
        resto = sum(int(d[i]) * (n + 1 - i) for i in range(n)) * 10 % 11 % 10
        if resto != int(d[n]):
            return False
    return True


def formatar_cpf(valor: str | None) -> str:
    """'12345678909' -> '123.456.789-09'; o que não tiver 11 dígitos volta como veio."""
    d = normalizar_doc(valor)
    if len(d) != 11:
        return (valor or "").strip()
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
