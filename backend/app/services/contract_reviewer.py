from __future__ import annotations

import json
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Voce e revisor de portugues juridico de um escritorio de advocacia brasileiro. "
    "Recebera uma lista de campos de texto livre digitados por quem preencheu um "
    "formulario de contrato de honorarios advocaticios (cada linha e' um campo "
    "isolado, rotulado — nao e' o contrato inteiro, entao nao aponte falta de "
    "contexto ou frases incompletas por si so). "
    "Aponte APENAS, dentro de cada campo: erros de portugues (ortografia, "
    "concordancia, crase, pontuacao), grafia informal/coloquial ou giria (ex.: "
    "'nois', 'vc', 'pq', 'ta'), termos fora do padrao formal juridico e frases "
    "confusas. Examine com atencao mesmo campos curtos de poucas palavras — nao "
    "deixe de apontar um erro so' por o campo ser curto. NAO opine sobre valores, "
    "percentuais, prazos ou o merito do conteudo. "
    "Liste no MAXIMO os 15 problemas mais relevantes, do mais para o menos grave. "
    "Responda SOMENTE com um JSON array (sem markdown, sem texto ao redor). Cada item: "
    '{"trecho": "citacao curta do texto original", "problema": "o que esta errado", '
    '"sugestao": "como corrigir"}. Se nao houver nada a apontar, responda [].'
)

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


class ContractReviewError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.deepseek_api_key)


def extract_open_fields(data: dict) -> str:
    """Extrai so' os campos de texto livre digitados no formulario (nao a clausula
    padrao do contrato, que quem preenche o wizard nao tem como editar ali)."""
    lines: list[str] = []

    def add(label: str, value) -> None:
        text = (value or "").strip() if isinstance(value, str) else ""
        if text:
            lines.append(f"{label}: {text}")

    for i, c in enumerate(data.get("contratantes") or [], 1):
        add(f"Contratante {i} - profissao", c.get("profissao"))

    for i, escopo in enumerate(data.get("escopos") or [], 1):
        prefix = f"Escopo {i}"
        add(f"{prefix} - descricao", escopo.get("descricao_custom"))
        add(f"{prefix} - demandas", escopo.get("demandas"))
        add(f"{prefix} - pessoas/patrimonios", escopo.get("pessoas_patrimonios"))
        add(f"{prefix} - tipo de reestruturacao", escopo.get("tipo_reestruturacao"))
        add(f"{prefix} - documentos", escopo.get("documentos"))
        add(f"{prefix} - consulta", escopo.get("consulta"))
        permuta = escopo.get("permuta") or {}
        add(f"{prefix} - permuta: descricao", permuta.get("descricao"))
        add(f"{prefix} - permuta: forma de pagamento da torna", permuta.get("forma_pagamento_torna"))

    acessorios = data.get("acessorios") or {}
    add("Limitacao do reembolso", acessorios.get("descricao_limitacao_reembolso"))
    add("Criterio de extincao do exito", acessorios.get("criterio_extincao_exito"))
    add("Clausulas adicionais", acessorios.get("clausulas_adicionais"))

    return "\n".join(lines)


def review_text(document_text: str) -> list[dict]:
    """Envia o texto do contrato para o DeepSeek (endpoint compativel Anthropic) e
    retorna divergencias de portugues/padrao. Levanta ContractReviewError se a API
    nao estiver configurada ou a chamada falhar."""
    if not is_configured():
        raise ContractReviewError("DEEPSEEK_API_KEY nao configurada")

    body = {
        "model": settings.deepseek_model,
        # deepseek-v4-pro pensa antes de responder (tokens de raciocinio ocultos
        # contam no orcamento) — com 4096 a resposta truncava antes do JSON fechar
        # e a revisao inteira era descartada. 16000 da folga pra textos maiores.
        "max_tokens": 16000,
        # temperature 0 = saida quase deterministica; o endpoint anthropic-compatible
        # da DeepSeek nao expoe seed, entao isto e' o maximo de consistencia possivel
        # (revisao de portugues nao precisa de criatividade).
        "temperature": 0,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": document_text[:60000]}],
    }
    headers = {
        "x-api-key": settings.deepseek_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        resp = httpx.post(
            f"{settings.deepseek_api_base}/v1/messages",
            json=body,
            headers=headers,
            # deepseek-v4-pro (thinking mode) demora bem mais que o modelo padrao.
            timeout=120.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("Falha ao chamar DeepSeek para revisao do contrato: %s", e)
        raise ContractReviewError(f"Falha ao chamar DeepSeek: {e}") from e

    data = resp.json()
    blocks = data.get("content", [])
    raw_text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    match = _JSON_ARRAY_RE.search(raw_text)
    if not match:
        logger.warning("Resposta do DeepSeek sem JSON array reconhecivel: %s", raw_text[:500])
        return []

    try:
        findings = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        logger.warning("JSON invalido na resposta do DeepSeek: %s", e)
        return []

    if not isinstance(findings, list):
        return []
    return [f for f in findings if isinstance(f, dict)]
