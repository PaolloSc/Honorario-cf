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


def test_concorrencia_otimista_409(client):
    v1 = client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 2}).json()["updated_at"]
    # aba A grava conhecendo v1 → ok, nova versão
    r = client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 3, "known_updated_at": v1})
    assert r.status_code == 200
    v2 = r.json()["updated_at"]
    assert v2 != v1
    # aba B ainda acha que é v1 → 409, não sobrescreve
    r = client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 6, "known_updated_at": v1})
    assert r.status_code == 409
    assert client.get("/api/drafts/abc12345").json()["current_step"] == 3
    # GET devolve a mesma string que o PUT, então quem retomou consegue gravar
    assert client.get("/api/drafts/abc12345").json()["updated_at"] == v2
    assert client.put("/api/drafts/abc12345", json={"form_data": FORM, "current_step": 4, "known_updated_at": v2}).status_code == 200


def test_put_tambem_apaga_vencidos_e_informa_expiracao(client):
    from datetime import datetime, timedelta

    from app.database import ContractDraftDB, SessionLocal

    db_session = SessionLocal()
    client.put("/api/drafts/velho0001", json={"form_data": FORM, "current_step": 2})
    d = db_session.query(ContractDraftDB).filter_by(draft_id="velho0001").one()
    d.updated_at = datetime.utcnow() - timedelta(days=91)
    db_session.commit()

    r = client.put("/api/drafts/novo00001", json={"form_data": FORM, "current_step": 1})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.query(ContractDraftDB).filter_by(draft_id="velho0001").first() is None

    s = r.json()
    assert datetime.fromisoformat(s["expires_at"]) - datetime.fromisoformat(s["updated_at"]) == timedelta(days=90)
    db_session.close()
