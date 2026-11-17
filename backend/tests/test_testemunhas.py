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
        json={"nome": "Lilian Silveira Correa", "email": "lilian@cf.com.br", "cpf": CPF},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["nome"] == "Lilian Silveira Correa"
    assert created["cpf"] == CPF
    assert created["ativo"] is True

    listed = client.get("/api/testemunhas").json()["testemunhas"]
    assert len(listed) == 1
    assert listed[0]["email"] == "lilian@cf.com.br"


CPF = "529.982.247-25"  # ficticio, com digitos verificadores validos


@pytest.mark.parametrize("cpf", [None, "", "123.456.789-00", "111.111.111-11"])
def test_cpf_obrigatorio_e_valido_no_cadastro(client, cpf):
    """Testemunha nova sem CPF, ou com CPF de verificador errado, nao entra no cadastro."""
    corpo = {"nome": "Fulana", "email": "f@b.com"}
    if cpf is not None:
        corpo["cpf"] = cpf
    assert client.post("/api/testemunhas", json=corpo).status_code == 422


def test_cpf_pode_ser_preenchido_depois_em_cadastro_antigo(client):
    """Quem ja' estava no cadastro (sem CPF) recebe o CPF por edicao; CPF invalido e' recusado."""
    from app.database import SessionLocal, TestemunhaDB

    db = SessionLocal()
    try:
        antiga = TestemunhaDB(nome="Antiga", email="antiga@b.com", ativo=True)
        db.add(antiga)
        db.commit()
        tid = antiga.id
    finally:
        db.close()

    assert client.get("/api/testemunhas").json()["testemunhas"][0]["cpf"] == ""
    assert client.patch(f"/api/testemunhas/{tid}", json={"cpf": "123"}).status_code == 422
    resp = client.patch(f"/api/testemunhas/{tid}", json={"cpf": "52998224725"})
    assert resp.status_code == 200 and resp.json()["cpf"] == CPF


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
        "/api/testemunhas", json={"nome": "Antigo", "email": "a@b.com", "cpf": CPF}
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
        "/api/testemunhas", json={"nome": "Some", "email": "some@b.com", "cpf": CPF}
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
