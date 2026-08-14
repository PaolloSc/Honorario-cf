"""Resolve qual modelo/gerador atende cada contrato.

Todo lugar que reconstroi um contrato a partir do form_data salvo (edicao,
regeneracao para o DocuSeal) passa por aqui, para que um tipo novo nao precise
ser lembrado em cada chamador.
"""

from __future__ import annotations

from typing import Any

from app.models.contract import ContratoRequest
from app.models.contrato_consumidor import TIPO_CONSUMIDOR_AEREO, ContratoConsumidorRequest
from app.services.consumidor_generator import ConsumidorGenerator
from app.services.contract_generator import ContractGenerator

TIPO_HONORARIOS = "honorarios"

_cache: dict[str, ContractGenerator] = {}


def get_generator(tipo: str = TIPO_HONORARIOS) -> ContractGenerator:
    if tipo not in _cache:
        _cache[tipo] = (
            ConsumidorGenerator() if tipo == TIPO_CONSUMIDOR_AEREO else ContractGenerator()
        )
    return _cache[tipo]


def tipo_contrato(form_data: dict) -> str:
    """Contratos salvos antes do segundo tipo nao tem o campo — sao de honorarios."""
    return form_data.get("tipo_contrato") or TIPO_HONORARIOS


def parse_form_data(form_data: dict) -> tuple[Any, ContractGenerator]:
    """Retorna (request validado, gerador) conforme o tipo gravado no form_data."""
    tipo = tipo_contrato(form_data)
    if tipo == TIPO_CONSUMIDOR_AEREO:
        return ContratoConsumidorRequest(**form_data), get_generator(tipo)
    return ContratoRequest(**form_data), get_generator(TIPO_HONORARIOS)
