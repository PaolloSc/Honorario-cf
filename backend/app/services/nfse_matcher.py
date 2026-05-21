"""Casa NF->contrato: CNPJ/CPF + periodo, fallback discriminacao `#contract_id`."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Protocol


class _ContractLike(Protocol):
    contract_id: str
    cliente_docs: list[str]
    data_inicio: object
    data_fim: object | None


class MatchStatus(str, Enum):
    AUTO = "auto"
    PENDENTE = "pendente"
    SEM_MATCH = "sem_match"


@dataclass
class MatchResult:
    status: MatchStatus
    contract_id: str | None = None
    candidatos: list[str] = field(default_factory=list)
    motivo: str | None = None


_ID_REGEX = re.compile(r"#?\b([a-f0-9-]{8,36})\b")


def _candidatos(nf, contratos: Iterable[_ContractLike]) -> list[_ContractLike]:
    out = []
    for contrato in contratos:
        if nf.tomador_doc not in (contrato.cliente_docs or []):
            continue
        if contrato.data_inicio > nf.competencia:
            continue
        if contrato.data_fim is not None and contrato.data_fim < nf.competencia:
            continue
        out.append(contrato)
    return out


def _ids_na_discriminacao(texto: str | None) -> set[str]:
    if not texto:
        return set()
    return {match.lower() for match in _ID_REGEX.findall(texto.lower())}


def match_nfse(nf, contratos: Iterable[_ContractLike]) -> MatchResult:
    candidatos = _candidatos(nf, contratos)
    if not candidatos:
        return MatchResult(MatchStatus.SEM_MATCH, motivo="nenhum contrato elegivel")
    if len(candidatos) == 1:
        return MatchResult(MatchStatus.AUTO, contract_id=candidatos[0].contract_id)

    ids = _ids_na_discriminacao(nf.discriminacao)
    if ids:
        hits = [contrato for contrato in candidatos if contrato.contract_id.lower() in ids]
        if len(hits) == 1:
            return MatchResult(MatchStatus.AUTO, contract_id=hits[0].contract_id, motivo="resolvido por #id")

    return MatchResult(
        MatchStatus.PENDENTE,
        candidatos=[contrato.contract_id for contrato in candidatos],
        motivo=f"{len(candidatos)} contratos candidatos sem desambiguacao",
    )
