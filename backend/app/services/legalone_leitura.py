"""Leitura (SO GET) do Legal One: partes de um processo ja cadastrado no escritorio.

Nunca grava nada no Legal One. Sem credenciais, ou com qualquer falha, devolve None em silencio:
quem chama segue com as partes digitadas.
"""
import logging
import os
import re
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = os.getenv("LEGALONE_API_TOKEN_URL", "https://api.thomsonreuters.com/legalone/oauth?grant_type=client_credentials")
BASE_URL = os.getenv("LEGALONE_API_BASE", "https://api.thomsonreuters.com/legalone/v1/api/rest")
TIMEOUT = 8  # a tela espera por isso: melhor sem preenchimento do que travada

_token: Optional[str] = None
_token_expira = 0.0
_CNJ = re.compile(r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$")


def _credenciais() -> Optional[tuple[str, str]]:
    cid, sec = os.getenv("LEGALONE_API_CLIENT_ID"), os.getenv("LEGALONE_API_CLIENT_SECRET")
    return (cid, sec) if cid and sec else None


def _get_token(cred: tuple[str, str]) -> Optional[str]:
    global _token, _token_expira
    if _token and time.time() < _token_expira:
        return _token
    r = httpx.post(TOKEN_URL, auth=cred, timeout=TIMEOUT)
    r.raise_for_status()
    corpo = r.json()
    _token = corpo.get("access_token")
    _token_expira = time.time() + int(corpo.get("expires_in", 3600)) - 60
    return _token


def partes_do_processo(numero_cnj: str) -> Optional[dict]:
    """{"cliente": [...], "contraria": [...]} do processo, ou None (sem credencial, nao achou, erro).

    numero_cnj precisa vir mascarado (cnj.normalizar): entra no $filter, entao e' conferido antes.
    """
    cred = _credenciais()
    if not cred or not _CNJ.match(numero_cnj):
        return None
    try:
        token = _get_token(cred)
        r = httpx.get(
            f"{BASE_URL}/Lawsuits",
            params={"$filter": f"identifierNumber eq '{numero_cnj}'", "$expand": "participants", "$top": 1},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        achados = r.json().get("value") or []
    except Exception as e:  # rede, 401, JSON: nao e' motivo para a tela falhar
        logger.warning("Legal One indisponivel para consulta de partes: %s", type(e).__name__)
        return None
    if not achados:
        return None
    participantes = achados[0].get("participants") or []

    def nomes(tipo: str) -> list[str]:
        vistos: list[str] = []
        for p in participantes:
            nome = (p.get("contactName") or "").strip()
            if p.get("type") == tipo and nome and nome not in vistos:
                vistos.append(nome)
        return vistos

    return {"cliente": nomes("Customer"), "contraria": nomes("OtherParty")}


def descricao(partes: dict) -> str:
    """'Cliente A e Cliente B x Parte Contraria' (vazio se o Legal One nao tem as duas pontas)."""
    if not partes or not partes["cliente"] or not partes["contraria"]:
        return ""
    return f"{' e '.join(partes['cliente'])} x {' e '.join(partes['contraria'])}"
