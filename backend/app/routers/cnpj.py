from __future__ import annotations

import re
import asyncio

import httpx
from fastapi import APIRouter, HTTPException

from app.utils.documento import normalizar_doc

router = APIRouter(prefix="/api/cnpj", tags=["cnpj"])


def _title_case(text: str) -> str:
    """Convert UPPERCASE text to Title Case, keeping common prepositions lowercase."""
    if not text:
        return text
    small_words = {"de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "a", "o", "as", "os", "por", "para", "com"}
    words = text.lower().split()
    result = []
    for i, word in enumerate(words):
        if i == 0 or word not in small_words:
            result.append(word.capitalize())
        else:
            result.append(word)
    return " ".join(result)


def _format_endereco(
    logradouro: str,
    numero: str,
    complemento: str,
    bairro: str,
    municipio: str,
    uf: str,
    cep: str,
) -> str:
    parts = [p for p in [_title_case(logradouro), numero, _title_case(complemento), _title_case(bairro)] if p]
    endereco = ", ".join(parts)
    if municipio:
        endereco += f", {_title_case(municipio)}/{uf.upper()}" if uf else f", {_title_case(municipio)}"
    if cep:
        clean_cep = re.sub(r"\D", "", cep)
        if len(clean_cep) == 8:
            cep = f"{clean_cep[:5]}-{clean_cep[5:]}"
        endereco += f", CEP {cep}"
    return endereco


def _parse_brasilapi(data: dict, cnpj_clean: str) -> dict:
    return {
        "cnpj": cnpj_clean,
        "razao_social": _title_case(data.get("razao_social", "") or ""),
        "nome_fantasia": _title_case(data.get("nome_fantasia", "") or ""),
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
        # Só a BrasilAPI traz o QSA; o CPF do sócio vem mascarado, por isso fica de fora.
        "socios": [
            {
                "nome": _title_case(s.get("nome_socio", "") or ""),
                "qualificacao": s.get("qualificacao_socio", "") or "",
            }
            for s in (data.get("qsa") or [])
            if s.get("nome_socio")
        ],
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
        "razao_social": _title_case(data.get("razao_social", "") or ""),
        "nome_fantasia": _title_case(estab.get("nome_fantasia", "") or ""),
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
        "razao_social": _title_case(company.get("name", "") or ""),
        "nome_fantasia": _title_case(data.get("alias", "") or ""),
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


def _escolher(resultados: list[dict | None], brasil_pronta: bool, todas_prontas: bool) -> dict | None:
    """Resultado a devolver, ou None se vale esperar mais. [0] é a BrasilAPI (única com QSA).

    Prefere a BrasilAPI; se ela veio sem endereço, completa com o de outra base. Sem
    endereço em nenhuma, só devolve quando todas terminaram (ou o prazo acabou)."""
    validos = [r for r in resultados if r and r.get("razao_social")]
    com_end = next((r for r in validos if r.get("endereco")), None)
    brasil = resultados[0] if resultados[0] and resultados[0].get("razao_social") else None
    if brasil and brasil.get("endereco"):
        return brasil
    if brasil and com_end:
        return {**brasil, "endereco": com_end["endereco"]}
    if com_end and brasil_pronta:
        return com_end
    if todas_prontas:
        return brasil or (validos[0] if validos else None)
    return None


@router.get("/{cnpj}")
async def lookup_cnpj(cnpj: str) -> dict:
    """Look up company data from public CNPJ APIs with fallback chain.

    Returns razao_social, endereco and other available data.
    """
    cnpj_clean = normalizar_doc(cnpj)

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
        brasilapi = tasks[0]
        pending = set(tasks)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 7.0
        try:
            # A BrasilAPI é a única com QSA: se ela responder dentro do prazo, ganha
            # mesmo chegando depois das outras; senão os sócios apareceriam só às vezes.
            # Resposta sem endereço não encerra a busca: espera as demais (até o prazo).
            while pending:
                done, pending = await asyncio.wait(
                    pending,
                    timeout=max(deadline - loop.time(), 0),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    break
                escolhido = _escolher([t.result() if t.done() else None for t in tasks], brasilapi.done(), not pending)
                if escolhido:
                    return escolhido
            escolhido = _escolher([t.result() if t.done() else None for t in tasks], True, True)
            if escolhido:
                return escolhido
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    raise HTTPException(
        status_code=404,
        detail="CNPJ nao encontrado nas bases publicas (BrasilAPI, cnpj.ws, cnpja).",
    )
