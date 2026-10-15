"""Contexto TLS com o certificado e-CNPJ A1 (.pfx) para o mTLS do ADN e do SEFIN.

O ssl do Python so carrega certificado de arquivo: a chave vai para um
diretorio temporario, cifrada com a propria senha, e o diretorio e apagado
assim que o contexto a carrega (antes de qualquer chamada de rede).

O .pfx do escritorio vem em BER (a `cryptography` le, com aviso) e sem a cadeia
intermediaria: `completar_cadeia` busca os emissores pelo AIA do certificado."""
from __future__ import annotations

import logging
import ssl
import tempfile
from pathlib import Path

import httpx
from cryptography import x509
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    NoEncryption,
    PrivateFormat,
    pkcs12,
    pkcs7,
)
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID

log = logging.getLogger("nfse-cert")


class CertificadoError(Exception):
    pass


def carregar_pfx(pfx: bytes, senha: str):
    """(chave, certificado, intermediarios) do .pfx; BER ou DER."""
    senha_b = senha.encode() if senha else None
    try:
        key, cert, extras = pkcs12.load_key_and_certificates(pfx, senha_b)
    except ValueError as e:
        # Nao repassa a mensagem original: so diz que o par pfx/senha nao abriu.
        raise CertificadoError("certificado .pfx invalido ou senha incorreta") from e
    if key is None or cert is None:
        raise CertificadoError("certificado .pfx sem chave privada")
    return key, cert, list(extras or [])


def _certs_da_resposta(corpo: bytes) -> list[x509.Certificate]:
    for ler in (
        lambda b: [x509.load_der_x509_certificate(b)],
        lambda b: [x509.load_pem_x509_certificate(b)],
        pkcs7.load_der_pkcs7_certificates,
        pkcs7.load_pem_pkcs7_certificates,
    ):
        try:
            return ler(corpo)
        except ValueError:
            continue
    return []


def completar_cadeia(cert: x509.Certificate, extras: list[x509.Certificate], max_niveis: int = 4):
    """Intermediarios do certificado: os do .pfx, ou os baixados do AIA (caIssuers).

    Melhor esforco: sem rede ou sem AIA, devolve o que ja tinha. A raiz
    (autoassinada) nao entra, o servidor ja a tem."""
    cadeia = list(extras)
    atual = cert
    for _ in range(max_niveis):
        if atual.issuer == atual.subject:
            break
        pai = next((c for c in cadeia if c.subject == atual.issuer), None)
        if pai is None:
            pai = _baixar_emissor(atual)
            if pai is None:
                break
            if pai.subject == pai.issuer:
                break
            cadeia.append(pai)
        atual = pai
    return cadeia


def _baixar_emissor(cert: x509.Certificate) -> x509.Certificate | None:
    try:
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
    except x509.ExtensionNotFound:
        return None
    for d in aia:
        url = d.access_location.value if isinstance(d.access_location, x509.UniformResourceIdentifier) else ""
        if d.access_method != AuthorityInformationAccessOID.CA_ISSUERS or not url.startswith(("http://", "https://")):
            continue
        try:
            r = httpx.get(url, timeout=10, follow_redirects=True)
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("cadeia: nao baixou o emissor (%s)", type(e).__name__)
            continue
        for c in _certs_da_resposta(r.content):
            if c.subject == cert.issuer:
                return c
    return None


def ssl_context_do_pfx(pfx: bytes, senha: str) -> ssl.SSLContext:
    senha_b = senha.encode() if senha else None
    key, cert, extras = carregar_pfx(pfx, senha)
    cadeia = completar_cadeia(cert, extras)

    cifra = BestAvailableEncryption(senha_b) if senha_b else NoEncryption()
    ctx = ssl.create_default_context()
    with tempfile.TemporaryDirectory(prefix="nfse-adn-") as d:
        cert_path, key_path = Path(d, "cert.pem"), Path(d, "key.pem")
        cert_path.write_bytes(b"".join(c.public_bytes(Encoding.PEM) for c in [cert, *cadeia]))
        key_path.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, cifra))
        ctx.load_cert_chain(cert_path, key_path, password=senha_b)
    return ctx
