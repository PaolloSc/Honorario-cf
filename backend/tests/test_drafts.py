"""Rascunhos do wizard (autosave no servidor)."""
import pytest

from app.auth import CurrentUser, get_current_user
from app.main import app

_usuario = {"email": "lawyer@test.com"}


def _fake_user():
    return CurrentUser(azure_id="t", email=_usuario["email"], name="Test", role="advogado")


@pytest.fixture(autouse=True)
def override_auth():
    _usuario["email"] = "lawyer@test.com"
    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


FORM = {"contratantes": [{"tipo": "PF", "nome": "Maria Souza"}], "escopos": []}


def test_upsert_e_leitura(client):
    r = client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 5})
    assert r.status_code == 200
    assert r.json()["client_name"] == "Maria Souza"
    assert r.json()["current_step"] == 5

    # segundo PUT com o mesmo id sobrescreve, não duplica
    client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 6})
    lista = client.get("/api/drafts").json()["drafts"]
    assert len(lista) == 1 and lista[0]["current_step"] == 6

    d = client.get("/api/drafts/abc12345").json()
    assert d["form_data"] == FORM


def test_rascunho_alheio_nao_aparece_nem_edita(client):
    client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 2})
    _usuario["email"] = "outra@test.com"
    assert client.get("/api/drafts").json()["drafts"] == []
    assert client.get("/api/drafts/abc12345").status_code == 404
    assert client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 2}).status_code == 404
    client.delete("/api/drafts/abc12345")  # não apaga o dos outros
    _usuario["email"] = "lawyer@test.com"
    assert client.get("/api/drafts/abc12345").status_code == 200


def test_delete_idempotente(client):
    client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 2})
    assert client.delete("/api/drafts/abc12345").status_code == 200
    assert client.delete("/api/drafts/abc12345").status_code == 200
    assert client.get("/api/drafts").json()["drafts"] == []


def test_id_invalido_e_passo_fora_da_faixa(client):
    assert client.put("/api/drafts/a", json={"form_data": FORM, "current_step": 1}).status_code == 422
    assert client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 9}).status_code == 422
