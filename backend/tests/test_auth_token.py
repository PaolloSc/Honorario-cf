"""Validação do JWT do Azure AD: skew de relógio, rotação de chave e 401 claro."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app import auth as auth_mod

TENANT = "tenant-de-teste"
AUDIENCE = "client-de-teste"


@pytest.fixture
def chave():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks(chave, kid: str) -> dict:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(chave.public_key(), as_dict=True)
    return {"keys": [{**jwk, "kid": kid, "use": "sig", "alg": "RS256"}]}


def _token(chave, kid: str, *, exp_delta: int = 3600) -> str:
    agora = int(time.time())
    return jwt.encode(
        {
            "oid": "oid-123",
            "preferred_username": "advogado@carvalhofurtadoadv.com.br",
            "name": "Advogado Teste",
            "aud": AUDIENCE,
            "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
            "iat": agora,
            "exp": agora + exp_delta,
        },
        chave,
        algorithm="RS256",
        headers={"kid": kid},
    )


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(auth_mod.settings, "azure_tenant_id", TENANT)
    monkeypatch.setattr(auth_mod.settings, "azure_auth_client_id", AUDIENCE)
    monkeypatch.setattr(auth_mod, "_jwks_cache", None)
    yield
    auth_mod._jwks_cache = None


def test_token_valido_decodifica(monkeypatch, chave):
    monkeypatch.setattr(auth_mod, "_fetch_jwks", lambda: _jwks(chave, "kid-1"))
    payload = auth_mod._decode_token(_token(chave, "kid-1"))
    assert payload["oid"] == "oid-123"


def test_skew_de_relogio_nao_derruba_token(monkeypatch, chave):
    """Backend alguns segundos adiantado não pode responder 401 'Token expirado'."""
    monkeypatch.setattr(auth_mod, "_fetch_jwks", lambda: _jwks(chave, "kid-1"))
    # Vencido há 30s — dentro da margem de 60s de _CLOCK_SKEW_LEEWAY_S.
    payload = auth_mod._decode_token(_token(chave, "kid-1", exp_delta=-30))
    assert payload["oid"] == "oid-123"


def test_token_realmente_vencido_da_401(monkeypatch, chave):
    monkeypatch.setattr(auth_mod, "_fetch_jwks", lambda: _jwks(chave, "kid-1"))
    with pytest.raises(HTTPException) as exc:
        auth_mod._decode_token(_token(chave, "kid-1", exp_delta=-7200))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token expirado"
    assert exc.value.headers["WWW-Authenticate"] == 'Bearer error="invalid_token"'


def test_jwks_recarrega_quando_azure_rotaciona_a_chave(monkeypatch, chave):
    """Cache eterno fazia todo request dar 401 até reiniciar o backend."""
    auth_mod._jwks_cache = _jwks(chave, "kid-antigo")
    chamadas = []

    def _refetch():
        chamadas.append(1)
        return _jwks(chave, "kid-novo")

    monkeypatch.setattr(auth_mod, "_fetch_jwks", _refetch)

    payload = auth_mod._decode_token(_token(chave, "kid-novo"))
    assert payload["oid"] == "oid-123"
    assert len(chamadas) == 1
    assert auth_mod._jwks_cache["keys"][0]["kid"] == "kid-novo"


def test_config_ausente_devolve_503_e_nao_401(monkeypatch):
    monkeypatch.setattr(auth_mod.settings, "azure_tenant_id", "")
    with pytest.raises(HTTPException) as exc:
        auth_mod._decode_token("a.b.c")
    assert exc.value.status_code == 503
