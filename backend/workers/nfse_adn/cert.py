"""Contexto TLS com o certificado e-CNPJ A1 (.pfx) para o mTLS do ADN.

O ssl do Python so carrega certificado de arquivo: a chave vai para um
diretorio temporario, cifrada com a propria senha, e o diretorio e apagado
assim que o contexto a carrega (antes de qualquer chamada de rede)."""
from __future__ import annotations

import ssl
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    NoEncryption,
    PrivateFormat,
    pkcs12,
)


class CertificadoError(Exception):
    pass


def ssl_context_do_pfx(pfx: bytes, senha: str) -> ssl.SSLContext:
    senha_b = senha.encode() if senha else None
    try:
        key, cert, extras = pkcs12.load_key_and_certificates(pfx, senha_b)
    except ValueError as e:
        # Nao repassa a mensagem original: so diz que o par pfx/senha nao abriu.
        raise CertificadoError("certificado .pfx invalido ou senha incorreta") from e
    if key is None or cert is None:
        raise CertificadoError("certificado .pfx sem chave privada")

    cifra = BestAvailableEncryption(senha_b) if senha_b else NoEncryption()
    ctx = ssl.create_default_context()
    with tempfile.TemporaryDirectory(prefix="nfse-adn-") as d:
        cert_path, key_path = Path(d, "cert.pem"), Path(d, "key.pem")
        cert_path.write_bytes(b"".join(c.public_bytes(Encoding.PEM) for c in [cert, *(extras or [])]))
        key_path.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, cifra))
        ctx.load_cert_chain(cert_path, key_path, password=senha_b)
    return ctx
