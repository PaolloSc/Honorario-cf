"""Distribuicao de DF-e do ADN: GET /DFe/{NSU}?lote=true ate acabar.

Formato da resposta (JSON) tirado de clientes da comunidade, ainda nao
conferido contra o Swagger oficial (que exige o certificado para abrir):
{StatusProcessamento, LoteDFe: [{NSU, ChaveAcesso, TipoDocumento, ArquivoXml}], Erros}.
ArquivoXml = XML compactado em gzip e codificado em base64. Aceita as chaves em
PascalCase e camelCase."""
from __future__ import annotations

import base64
import gzip
from typing import Iterator

import httpx


class ADNError(Exception):
    pass


def _campo(d: dict, nome: str):
    return d.get(nome, d.get(nome[0].lower() + nome[1:]))


def _acabou(r: httpx.Response, corpo: dict) -> bool:
    if r.status_code == 404:
        return True
    if _campo(corpo, "StatusProcessamento") == "NENHUM_DOCUMENTO_LOCALIZADO":
        return True
    # E2215: "Nenhum documento localizado ... a partir do NSU informado".
    return r.status_code == 400 and "E2215" in r.text


def lotes(http: httpx.Client, nsu: int) -> Iterator[list[tuple[int, bytes]]]:
    """Lotes de (NSU, xml) com NSU > nsu, em ordem, ate o ADN nao ter mais nada."""
    while True:
        r = http.get(f"/DFe/{nsu}", params={"lote": "true"})
        try:
            corpo = r.json() if r.content else {}
        except ValueError:
            corpo = {}
        if not isinstance(corpo, dict):
            corpo = {}
        if _acabou(r, corpo):
            return
        status = _campo(corpo, "StatusProcessamento")
        if r.status_code >= 400 or status == "REJEICAO":
            raise ADNError(f"ADN respondeu {r.status_code} {status}: {_campo(corpo, 'Erros') or r.text[:300]}")

        docs = []
        for item in _campo(corpo, "LoteDFe") or []:
            n = int(_campo(item, "NSU"))
            if n <= nsu:  # o ADN pode devolver o proprio NSU pedido
                continue
            try:
                docs.append((n, gzip.decompress(base64.b64decode(_campo(item, "ArquivoXml")))))
            except (ValueError, OSError, TypeError) as e:
                raise ADNError(f"ArquivoXml ilegivel no NSU {n}: {e}") from e
        if not docs:
            return
        docs.sort()
        yield docs
        nsu = docs[-1][0]
