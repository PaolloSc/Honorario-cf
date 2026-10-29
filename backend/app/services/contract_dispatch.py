"""Resolve qual modelo/gerador atende cada contrato.

Todo lugar que reconstroi um contrato a partir do form_data salvo (edicao,
regeneracao para o DocuSeal) passa por aqui, para que um tipo novo nao precise
ser lembrado em cada chamador.
"""

from __future__ import annotations

from typing import Any

from app.models.contract import ContratoRequest
from app.models.contrato_consumidor import TIPO_CONSUMIDOR_AEREO, ContratoConsumidorRequest
from app.models.documentos_complementares import (
    REQUESTS as REQUESTS_COMPLEMENTARES,
    TIPO_ADITIVO,
    TIPO_DISTRATO,
    TIPO_SUBSTABELECIMENTO,
)
from app.services.complementares_generator import (
    AditivoGenerator,
    DistratoGenerator,
    SubstabelecimentoGenerator,
)
from app.services.consumidor_generator import ConsumidorGenerator
from app.services.contract_generator import ContractGenerator

TIPO_HONORARIOS = "honorarios"

_GERADORES: dict[str, type[ContractGenerator]] = {
    TIPO_CONSUMIDOR_AEREO: ConsumidorGenerator,
    TIPO_ADITIVO: AditivoGenerator,
    TIPO_DISTRATO: DistratoGenerator,
    TIPO_SUBSTABELECIMENTO: SubstabelecimentoGenerator,
}

_cache: dict[str, ContractGenerator] = {}


def get_generator(tipo: str = TIPO_HONORARIOS) -> ContractGenerator:
    if tipo not in _cache:
        _cache[tipo] = _GERADORES.get(tipo, ContractGenerator)()
    return _cache[tipo]


def tipo_contrato(form_data: dict) -> str:
    """Contratos salvos antes do segundo tipo nao tem o campo — sao de honorarios."""
    return form_data.get("tipo_contrato") or TIPO_HONORARIOS


def parse_form_data(form_data: dict, estrito: bool = False) -> tuple[Any, ContractGenerator]:
    """Retorna (request validado, gerador) conforme o tipo gravado no form_data.
    estrito=True (edicao de contrato salvo) aplica as mesmas validacoes do contrato novo;
    o padrao e' brando, para regerar contratos antigos (download, e-mail, assinatura)."""
    tipo = tipo_contrato(form_data)
    if tipo == TIPO_CONSUMIDOR_AEREO:
        return ContratoConsumidorRequest(**form_data), get_generator(tipo)
    if tipo in REQUESTS_COMPLEMENTARES:
        return REQUESTS_COMPLEMENTARES[tipo](**form_data), get_generator(tipo)
    ctx = None if estrito else {"previa": True}
    return ContratoRequest.model_validate(form_data, context=ctx), get_generator(TIPO_HONORARIOS)
