"""OAB de um advogado do cadastro de colaboradores: numero (so digitos) e UF."""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, field_validator

UFS = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
)


class OabItem(BaseModel):
    numero: str
    uf: str

    @field_validator("numero")
    @classmethod
    def _so_digitos(cls, v: str) -> str:
        v = re.sub(r"[.\s]", "", v or "")
        if not re.fullmatch(r"\d{1,7}", v):
            raise ValueError("Número da OAB deve ter só dígitos")
        return v

    @field_validator("uf")
    @classmethod
    def _uf_valida(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if v not in UFS:
            raise ValueError("UF inválida")
        return v


def oabs_de_json(texto: str | None) -> list[OabItem]:
    """Coluna colaboradores.oabs -> lista; vazio ou JSON ruim viram lista vazia."""
    if not texto:
        return []
    try:
        return [OabItem(**x) for x in json.loads(texto)]
    except (ValueError, TypeError):
        return []


def oabs_para_json(oabs: list[OabItem] | None) -> str | None:
    return json.dumps([o.model_dump() for o in oabs], ensure_ascii=False) if oabs else None
