"""Certificado A1 do emissor em repouso: o .pfx (base64) e a senha cifrados com a KEK (AES-GCM),
no mesmo padrao de credencial_pbh. So decifra em memoria, na hora de assinar/enviar."""
from __future__ import annotations

import base64
import re

from app.config import settings
from app.models.emissao_db import EmissorConfigDB
from app.services.crypto import CryptoBox, EncryptedBlob


def cnpjs_do_certificado(cert) -> set[str]:
    """CNPJs (14 digitos isolados) no subject do certificado e-CNPJ (CN 'NOME:00000000000000')."""
    return set(re.findall(r"(?<!\d)\d{14}(?!\d)", cert.subject.rfc4514_string()))


def _box() -> CryptoBox:
    if not settings.nfse_kek:
        raise RuntimeError("NFSE_KEK nao configurada")
    return CryptoBox(settings.nfse_kek)


def guardar_certificado(cfg: EmissorConfigDB, pfx: bytes, senha: str) -> None:
    box = _box()
    pfx_blob = box.encrypt(base64.b64encode(pfx).decode())
    senha_blob = box.encrypt(senha)
    cfg.cert_pfx_enc, cfg.cert_pfx_nonce = pfx_blob.ciphertext, pfx_blob.nonce
    cfg.cert_senha_enc, cfg.cert_senha_nonce = senha_blob.ciphertext, senha_blob.nonce


def tem_certificado(cfg: EmissorConfigDB) -> bool:
    return bool(cfg.cert_pfx_enc and cfg.cert_senha_enc)


def decifrar_certificado(cfg: EmissorConfigDB) -> tuple[bytes, str]:
    """(pfx, senha) em memoria. Nunca logar, nem devolver em resposta ou evento."""
    box = _box()
    pfx = base64.b64decode(box.decrypt(EncryptedBlob(cfg.cert_pfx_nonce, cfg.cert_pfx_enc)))
    senha = box.decrypt(EncryptedBlob(cfg.cert_senha_nonce, cfg.cert_senha_enc))
    return pfx, senha
