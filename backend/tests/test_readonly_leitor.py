"""Guard do papel 'leitor': 403 em escrita, livre em leitura."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import CurrentUser, _enforce_readonly


def _req(method: str):
    return SimpleNamespace(method=method)  # _enforce_readonly só lê .method


def _user(role: str):
    return CurrentUser(azure_id="x", email="x@e", name="X", role=role)


def test_leitor_bloqueado_em_escrita():
    for m in ("POST", "PUT", "PATCH", "DELETE"):
        with pytest.raises(HTTPException) as e:
            _enforce_readonly(_req(m), _user("leitor"))
        assert e.value.status_code == 403


def test_leitor_livre_em_leitura():
    for m in ("GET", "HEAD", "OPTIONS"):
        assert _enforce_readonly(_req(m), _user("leitor")).role == "leitor"


def test_outros_papeis_escrevem():
    for role in ("admin", "advogado", "financeiro"):
        assert _enforce_readonly(_req("POST"), _user(role)).role == role
