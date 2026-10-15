"""Chamadas ao SEFIN Nacional, PRODUCAO RESTRITA: POST /nfse, GET /dps/{id}, GET /nfse/{chave}.

Compartilhado pelo smoke (run.py, que imprime) e pelo servico de emissao do app (que grava).
O host e fixo no codigo e nao ha opcao para trocar por producao."""
from __future__ import annotations

import base64
import gzip
import re
from dataclasses import dataclass, field

import httpx
from lxml import etree

SEFIN_HOST = "https://sefin.producaorestrita.nfse.gov.br"
# A documentacao (/API/SefinNacional/docs) e os relatos (/SefinNacional/nfse) divergem
# no prefixo. Tenta um e, so se a rota nao existir (404 sem JSON), o outro.
SEFIN_BASES = (f"{SEFIN_HOST}/SefinNacional", f"{SEFIN_HOST}/API/SefinNacional")


def campo(d: dict, nome: str):
    return d.get(nome, d.get(nome[0].lower() + nome[1:]))


def corpo_json(r: httpx.Response) -> dict:
    try:
        corpo = r.json()
    except ValueError:
        return {}
    return corpo if isinstance(corpo, dict) else {}


def uma_linha(texto: str) -> str:
    """Texto do servidor numa linha so e sem '::': o Actions le '::cmd::' no inicio da linha
    como comando de workflow (add-mask, error...)."""
    return re.sub(r"\s+", " ", texto).replace("::", ": :")


def erros_do_corpo(corpo: dict) -> list[tuple[str, str]]:
    brutos = campo(corpo, "Erros") or campo(corpo, "Erro") or []
    if isinstance(brutos, dict):
        brutos = [brutos]
    saida = []
    for e in brutos if isinstance(brutos, list) else []:
        if isinstance(e, dict):
            saida.append((str(campo(e, "Codigo") or "?"), str(campo(e, "Descricao") or campo(e, "Mensagem") or "")))
    return saida


def xml_da_nota(corpo: dict) -> bytes | None:
    b64 = campo(corpo, "NfseXmlGZipB64")
    if not b64:
        return None
    try:
        return gzip.decompress(base64.b64decode(b64))
    except (ValueError, OSError):
        return None


def chave_do_corpo(corpo: dict) -> str | None:
    chave = campo(corpo, "ChaveAcesso")
    if chave:
        return str(chave)
    xml = xml_da_nota(corpo)
    if xml is None:
        return None
    try:
        inf = etree.fromstring(xml).find(".//{*}infNFSe")
        return inf.get("Id").removeprefix("NFS") if inf is not None else None
    except (etree.XMLSyntaxError, AttributeError):
        return None


@dataclass
class Resposta:
    status: int
    corpo: dict = field(default_factory=dict)
    texto: str = ""
    base: str | None = None

    @property
    def chave(self) -> str | None:
        return chave_do_corpo(self.corpo)

    @property
    def erros(self) -> list[tuple[str, str]]:
        return erros_do_corpo(self.corpo)

    @property
    def sucesso(self) -> bool:
        return 200 <= self.status < 300 and self.chave is not None


def _responder(r: httpx.Response, base: str) -> Resposta:
    return Resposta(r.status_code, corpo_json(r), r.text, base)


def _pedir(http: httpx.Client, metodo: str, caminho: str, avisar=lambda msg: None, **kw) -> Resposta:
    """Tenta o 1o prefixo e, so se a rota nao existir (404 sem JSON), o 2o. Rejeicao e erro de
    rede nunca trocam de prefixo (nem reenviam)."""
    for i, base in enumerate(SEFIN_BASES):
        r = http.request(metodo, f"{base}{caminho}", **kw)
        if r.status_code == 404 and not corpo_json(r) and i < len(SEFIN_BASES) - 1:
            avisar(f"{base}{caminho}: 404 (rota inexistente), tentando o outro prefixo")
            continue
        return _responder(r, base)
    raise AssertionError("inalcancavel")


def post_dps(http: httpx.Client, dps_assinado: bytes, avisar=lambda msg: None) -> Resposta:
    corpo = {"dpsXmlGZipB64": base64.b64encode(gzip.compress(dps_assinado, mtime=0)).decode()}
    return _pedir(http, "POST", "/nfse", avisar, json=corpo)


def get_dps(http: httpx.Client, id_dps: str) -> Resposta:
    """GET /dps/{id}: chave de acesso da NFS-e gerada para a DPS (so o certificado que consta na nota)."""
    return _pedir(http, "GET", f"/dps/{id_dps}")


def get_nfse(http: httpx.Client, chave: str) -> Resposta:
    return _pedir(http, "GET", f"/nfse/{chave}")
