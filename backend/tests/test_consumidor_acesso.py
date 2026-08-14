"""Acesso ao contrato de Ação de Consumo: restrito à equipe indicada."""

import pytest

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.main import app
from tests.test_consumidor_generator import DOIS


@pytest.fixture
def allowlist():
    original = settings.consumidor_emails
    settings.consumidor_emails = "monica@cf.com.br, Marcela@CF.com.br"
    yield
    settings.consumidor_emails = original


def _como(email: str, role: str = "advogado"):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email=email, name="Teste", role=role
    )


@pytest.fixture(autouse=True)
def _limpa_override():
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_pessoa_da_lista_gera(client, allowlist):
    _como("monica@cf.com.br")
    assert client.post("/api/contract/preview-consumidor", json=DOIS).status_code == 200


def test_email_da_lista_ignora_maiusculas(client, allowlist):
    _como("marcela@cf.com.br")
    assert client.get("/api/contract/consumidor/acesso").json() == {"permitido": True}


def test_advogado_de_fora_e_bloqueado(client, allowlist):
    _como("outro@cf.com.br")
    assert client.post("/api/contract/preview-consumidor", json=DOIS).status_code == 403
    assert client.post("/api/contract/generate-consumidor", json=DOIS).status_code == 403
    assert client.get("/api/contract/consumidor/acesso").json() == {"permitido": False}


def test_admin_sempre_pode(client, allowlist):
    _como("chefe@cf.com.br", role="admin")
    assert client.get("/api/contract/consumidor/acesso").json() == {"permitido": True}


def test_lista_vazia_libera_so_admin(client):
    original = settings.consumidor_emails
    settings.consumidor_emails = ""
    try:
        _como("qualquer@cf.com.br")
        assert client.get("/api/contract/consumidor/acesso").json() == {"permitido": False}
        _como("chefe@cf.com.br", role="admin")
        assert client.get("/api/contract/consumidor/acesso").json() == {"permitido": True}
    finally:
        settings.consumidor_emails = original
