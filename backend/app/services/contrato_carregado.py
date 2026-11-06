"""Contrato carregado (GLOSSARY.md): a versao salva de um contrato ja decodificada.

Todo lugar que reconstroi um contrato a partir do form_data salvo (edicao,
download, e-mail, regeneracao para o DocuSeal) passa por aqui e recebe de uma vez o tipo
(honorarios, consumidor aereo, aditivo, distrato, substabelecimento), o request validado, o
gerador e o cliente. Um tipo novo nao precisa ser lembrado em cada chamador.

Modo da validacao: brando (padrao) regera contratos antigos sem recusar; estrito (edicao de
contrato salvo) aplica as mesmas regras do contrato novo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.database import ContractVersionDB

from app.models.contract import ContratoRequest
from app.models.contrato_consumidor import TIPO_CONSUMIDOR_AEREO, ContratoConsumidorRequest
from app.models.documentos_complementares import (
    REQUESTS as REQUESTS_COMPLEMENTARES,
    TIPO_ADITIVO,
    TIPO_DISTRATO,
    TIPO_SUBSTABELECIMENTO,
    email_contato,
    nome_exibicao,
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


def tipo_da_versao(form_data_json: str | None) -> str:
    """Tipo gravado numa versao; vazio ou ilegivel conta como honorarios (contratos antigos)."""
    if not form_data_json:
        return TIPO_HONORARIOS
    try:
        return tipo_contrato(json.loads(form_data_json))
    except (ValueError, TypeError):
        return TIPO_HONORARIOS


def cliente_do_form_data(form_data: dict) -> tuple[str, str]:
    """(nome, e-mail) do cliente para listagem e busca. Aditivo/distrato guardam os contratantes;
    o substabelecimento, o outorgante."""
    tipo = form_data.get("tipo_contrato")
    if tipo in REQUESTS_COMPLEMENTARES:
        parsed = REQUESTS_COMPLEMENTARES[tipo](**form_data)
        return (nome_exibicao(parsed), email_contato(parsed))
    contratantes = form_data.get("contratantes", [])
    if not contratantes:
        return ("", "")
    first = contratantes[0]
    return (first.get("nome") or first.get("razao_social") or "", first.get("email", ""))


def ultima_versao(db: Session, contract_id: str, numero: int | None = None) -> ContractVersionDB | None:
    """A versao pedida do contrato; sem numero, a mais nova."""
    q = db.query(ContractVersionDB).filter(ContractVersionDB.contract_id == contract_id)
    if numero is not None:
        return q.filter(ContractVersionDB.version_number == numero).first()
    return q.order_by(ContractVersionDB.version_number.desc()).first()


@dataclass
class ContratoCarregado:
    versao: ContractVersionDB
    form_data: dict
    tipo: str
    request: Any
    gerador: ContractGenerator

    @property
    def cliente(self) -> tuple[str, str]:
        return cliente_do_form_data(self.form_data)


def carregar_versao(versao: ContractVersionDB, estrito: bool = False) -> ContratoCarregado:
    """Decodifica uma versao ja lida. Levanta o erro do pydantic/JSON se os dados nao servem."""
    form_data = json.loads(versao.form_data_json)
    request, gerador = parse_form_data(form_data, estrito=estrito)
    return ContratoCarregado(versao, form_data, tipo_contrato(form_data), request, gerador)


def carregar(db: Session, contract_id: str, numero: int | None = None, estrito: bool = False) -> ContratoCarregado | None:
    """Le e decodifica a versao do contrato (a mais nova se `numero` for omitido); None se nao existe."""
    versao = ultima_versao(db, contract_id, numero)
    return carregar_versao(versao, estrito) if versao else None
