"""Enums SAP-like para classificacao de pagamentos."""
from __future__ import annotations

TIPOS_COBRANCA = ("mensal", "hora", "avulso", "exito", "prolabore", "partido")
NATUREZAS_PAGAMENTO = ("captacao", "performance", "captacao_performance", "projeto_opt")
TIPOS_DOCUMENTO = ("nf", "emitir", "recebimento_manual", "recibo")


def validar_tipo_cobranca(v: str | None) -> bool:
    return v is None or v in TIPOS_COBRANCA


def validar_natureza_pagamento(v: str | None) -> bool:
    return v is None or v in NATUREZAS_PAGAMENTO


def validar_tipo_documento(v: str) -> bool:
    return v in TIPOS_DOCUMENTO
