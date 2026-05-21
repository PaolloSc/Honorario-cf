import base64
import os

import pytest

from app.services.crypto import CryptoBox, InvalidCipherError


@pytest.fixture
def kek_b64() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def test_roundtrip(kek_b64):
    box = CryptoBox(kek_b64)
    plaintext = "minha-senha-pbh-123!@#"
    blob = box.encrypt(plaintext)
    assert box.decrypt(blob) == plaintext


def test_distinct_nonces_per_write(kek_b64):
    box = CryptoBox(kek_b64)
    a = box.encrypt("x")
    b = box.encrypt("x")
    assert a.nonce != b.nonce
    assert a.ciphertext != b.ciphertext


def test_wrong_key_fails(kek_b64):
    box1 = CryptoBox(kek_b64)
    blob = box1.encrypt("hello")
    other = base64.b64encode(os.urandom(32)).decode()
    box2 = CryptoBox(other)
    with pytest.raises(InvalidCipherError):
        box2.decrypt(blob)


def test_tampered_ciphertext_fails(kek_b64):
    box = CryptoBox(kek_b64)
    blob = box.encrypt("hello")
    tampered = type(blob)(nonce=blob.nonce, ciphertext=blob.ciphertext[:-1] + b"\x00")
    with pytest.raises(InvalidCipherError):
        box.decrypt(tampered)


def test_invalid_kek_length():
    bad = base64.b64encode(os.urandom(16)).decode()
    with pytest.raises(ValueError):
        CryptoBox(bad)
