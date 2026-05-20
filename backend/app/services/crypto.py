"""AES-GCM envelope encryption para credenciais PBH em repouso."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class InvalidCipherError(Exception):
    """Raised when decryption fails."""


@dataclass(frozen=True)
class EncryptedBlob:
    nonce: bytes
    ciphertext: bytes


class CryptoBox:
    NONCE_LEN = 12

    def __init__(self, kek_b64: str) -> None:
        key = base64.b64decode(kek_b64)
        if len(key) != 32:
            raise ValueError(f"KEK deve ter 32 bytes, recebido {len(key)}")
        self._aead = AESGCM(key)

    def encrypt(self, plaintext: str) -> EncryptedBlob:
        nonce = os.urandom(self.NONCE_LEN)
        ciphertext = self._aead.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
        return EncryptedBlob(nonce=nonce, ciphertext=ciphertext)

    def decrypt(self, blob: EncryptedBlob) -> str:
        try:
            plaintext = self._aead.decrypt(blob.nonce, blob.ciphertext, associated_data=None)
        except InvalidTag as e:
            raise InvalidCipherError("falha ao decifrar") from e
        return plaintext.decode("utf-8")
