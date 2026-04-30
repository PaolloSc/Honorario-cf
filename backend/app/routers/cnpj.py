from __future__ import annotations

import re
import asyncio

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/cnpj", tags=["cnpj"])


def _format_endereco(
    logradouro: str,
    numero: str,
    complemento: str,
    bairro: str,
    municipio: str,
    uf: str,
    cep: str,
) -> str:
    parts = [p for p in [logradouro, numero, complemento, bairro] if p]
    endereco = ", ".join(parts)
    if municipio:
        endereco += f", {municipio}/{uf}" if uf else f", {municipio}"
    if cep:
        endereco += f", CEP {cep}"
    return endereco


def _parse_brasilapi(data: dict, cnpj_clean: str) -> dict:
    return {
        "cnpj": cnpj_clean,
        "razao_social": data.get("razao_social", "") or "",
        "nome_fantasia": data.get("nome_fantasia", "") or "",
        "endereco": _format_endereco(
            data.get("logradouro", "") or "",
            data.get("numero", "") or "",
            data.get("complemento", "") or "",
            data.get("bairro", "") or "",
            data.get("municipio", "") or "",
            data.get("uf", "") or "",
            data.get("cep", "") or "",
        ),
        "situacao_cadastral": data.get("descricao_situacao_cadastral", "") or "",
        "natureza_juridica": data.get("natureza_juridica", "") or "",
    }


def _parse_publica_cnpj_ws(data: dict, cnpj_clean: str) -> dict:
    estab = data.get("estabelecimento") or {}
    natureza = data.get("natureza_juridica") or {}
    cidade = estab.get("cidade") or {}
    estado = estab.get("estado") or {}

    tipo_logradouro = estab.get("tipo_logradouro", "") or ""
    logradouro = estab.get("logradouro", "") or ""
    full_logradouro = (
        f"{tipo_logradouro} {logradouro}".strip() if tipo_logradouro else logradouro
    )

    return {
        "cnpj": cnpj_clean,
        "razao_social": data.get("razao_social", "") or "",
        "nome_fantasia": estab.get("nome_fantasia", "") or "",
        "endereco": _format_endereco(
            full_logradouro,
            estab.get("numero", "") or "",
            estab.get("complemento", "") or "",
            estab.get("bairro", "") or "",
            cidade.get("nome", "") or "",
            estado.get("sigla", "") or "",
            estab.get("cep", "") or "",
        ),
        "situacao_cadastral": estab.get("situacao_cadastral", "") or "",
        "natureza_juridica": natureza.get("descricao", "") or "",
    }


def _parse_open_cnpja(data: dict, cnpj_clean: str) -> dict:
    company = data.get("company") or {}
    address = data.get("address") or {}
    state = address.get("state") or {}
    nature = company.get("nature") or {}

    return {
        "cnpj": cnpj_clean,
        "razao_social": company.get("name", "") or "",
        "nome_fantasia": data.get("alias", "") or "",
        "endereco": _format_endereco(
            address.get("street", "") or "",
            str(address.get("number", "") or ""),
            address.get("details", "") or "",
            address.get("district", "") or "",
            address.get("city", "") or "",
            (state if isinstance(state, str) else state.get("sigla", "")) or "",
            address.get("zip", "") or "",
        ),
        "situacao_cadastral": (data.get("status") or {}).get("text", "") or "",
        "natureza_juridica": nature.get("text", "") or "",
    }


async def _try_source(
    client: httpx.AsyncClient, url: str, parser, cnpj_clean: str
) -> dict | None:
    try:
        response = await client.get(url)
    except httpx.RequestError:
        return None
    if response.status_code != 200:
        return None
    try:
        return parser(response.json(), cnpj_clean)
    except (ValueError, KeyError, AttributeError, TypeError):
        return None


@router.get("/{cnpj}")
async def lookup_cnpj(cnpj: str) -> dict:
    """Look up company data from public CNPJ APIs with fallback chain.

    Returns razao_social, endereco and other available data.
    """
    cnpj_clean = re.sub(r"\D", "", cnpj)

    if len(cnpj_clean) != 14:
        raise HTTPException(status_code=400, detail="CNPJ invalido")

    sources = [
        (
            f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_clean}",
            _parse_brasilapi,
        ),
        (
            f"https://publica.cnpj.ws/cnpj/{cnpj_clean}",
            _parse_publica_cnpj_ws,
        ),
        (
            f"https://open.cnpja.com/office/{cnpj_clean}",
            _parse_open_cnpja,
        ),
    ]

    timeout = httpx.Timeout(6.0, connect=3.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = [
            asyncio.create_task(_try_source(client, url, parser, cnpj_clean))
            for url, parser in sources
        ]
        try:
            for task in asyncio.as_completed(tasks, timeout=7.0):
                result = await task
                if result and result.get("razao_social"):
                    for pending in tasks:
                        if not pending.done():
                            pending.cancel()
                    return result
        except TimeoutError:
            pass
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    raise HTTPException(
        status_code=404,
        detail="CNPJ nao encontrado nas bases publicas (BrasilAPI, cnpj.ws, cnpja).",
    )
