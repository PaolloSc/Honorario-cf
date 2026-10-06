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
