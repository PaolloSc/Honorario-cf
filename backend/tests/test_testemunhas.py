"""Testes do CRUD do roster de testemunhas."""
import pytest

from app.auth import CurrentUser, get_current_user
from app.main import app


def _fake_user():
    return CurrentUser(
        azure_id="t-azure",
        email="lawyer@test.com",
        name="Test Lawyer",
        role="advogado",
    )


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_create_and_list(client):
    resp = client.post(
        "/api/testemunhas",
        json={"nome": "Lilian Siqueira", "email": "lilian@cf.com.br"},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["nome"] == "Lilian Siqueira"
    assert created["ativo"] is True

    listed = client.get("/api/testemunhas").json()["testemunhas"]
    assert len(listed) == 1
    assert listed[0]["email"] == "lilian@cf.com.br"


def test_invalid_email_rejected(client):
    resp = client.post(
        "/api/testemunhas",
        json={"nome": "Fulano", "email": "nao-eh-email"},
    )
    assert resp.status_code == 422


def test_empty_nome_rejected(client):
    resp = client.post(
        "/api/testemunhas",
        json={"nome": "   ", "email": "x@y.com"},
    )
    assert resp.status_code == 422


def test_patch_updates_fields(client):
    tid = client.post(
        "/api/testemunhas", json={"nome": "Antigo", "email": "a@b.com"}
    ).json()["id"]

    resp = client.patch(
        f"/api/testemunhas/{tid}",
        json={"nome": "Novo Nome", "email": "novo@b.com"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome"] == "Novo Nome"
    assert body["email"] == "novo@b.com"


def test_soft_delete_hides_from_default_list(client):
    tid = client.post(
        "/api/testemunhas", json={"nome": "Some", "email": "some@b.com"}
    ).json()["id"]

    client.patch(f"/api/testemunhas/{tid}", json={"ativo": False})

    # Default list: only active -> empty
    assert client.get("/api/testemunhas").json()["testemunhas"] == []
    # include_inactive=True -> shows it
    all_rows = client.get("/api/testemunhas?include_inactive=true").json()["testemunhas"]
    assert len(all_rows) == 1
    assert all_rows[0]["ativo"] is False


def test_patch_404_when_missing(client):
    resp = client.patch("/api/testemunhas/9999", json={"ativo": False})
    assert resp.status_code == 404
