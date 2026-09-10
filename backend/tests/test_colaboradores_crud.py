"""CRUD admin do roster de colaboradores (/api/colaboradores)."""
import pytest

from app.auth import CurrentUser, get_current_user
from app.main import app


def _admin():
    return CurrentUser(azure_id="a", email="admin@cf.com", name="Admin", role="admin")


def _advogado():
    return CurrentUser(azure_id="b", email="adv@cf.com", name="Adv", role="advogado")


@pytest.fixture
def as_admin():
    app.dependency_overrides[get_current_user] = _admin
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_crud_requires_admin(client):
    app.dependency_overrides[get_current_user] = _advogado
    try:
        assert client.get("/api/colaboradores").status_code == 403
        assert client.post(
            "/api/colaboradores", json={"nome": "X", "papel": "advogado"}
        ).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_create_and_list(client, as_admin):
    resp = client.post(
        "/api/colaboradores",
        json={"nome": "Caio Cesar", "email": "caio@cf.com", "papel": "socio", "ordem": 1},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["nome"] == "Caio Cesar"
    assert body["papel"] == "socio"
    assert body["participavel"] is True
    assert body["ativo"] is True

    listed = client.get("/api/colaboradores").json()["colaboradores"]
    assert len(listed) == 1


def test_create_email_optional(client, as_admin):
    resp = client.post("/api/colaboradores", json={"nome": "Sem Email", "papel": "advogado"})
    assert resp.status_code == 201
    assert resp.json()["email"] is None


def test_invalid_papel_rejected(client, as_admin):
    resp = client.post("/api/colaboradores", json={"nome": "X", "papel": "rei"})
    assert resp.status_code == 422


def test_invalid_email_rejected(client, as_admin):
    resp = client.post(
        "/api/colaboradores", json={"nome": "X", "papel": "advogado", "email": "nao-eh"}
    )
    assert resp.status_code == 422


def test_empty_nome_rejected(client, as_admin):
    resp = client.post("/api/colaboradores", json={"nome": "  ", "papel": "advogado"})
    assert resp.status_code == 422


def test_patch_updates_fields(client, as_admin):
    cid = client.post(
        "/api/colaboradores", json={"nome": "Antigo", "papel": "estagiario"}
    ).json()["id"]
    resp = client.patch(
        f"/api/colaboradores/{cid}",
        json={"nome": "Novo", "papel": "advogado", "email": "novo@cf.com"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nome"] == "Novo"
    assert body["papel"] == "advogado"
    assert body["participavel"] is True


def test_soft_delete(client, as_admin):
    cid = client.post(
        "/api/colaboradores", json={"nome": "Some", "papel": "advogado"}
    ).json()["id"]
    resp = client.delete(f"/api/colaboradores/{cid}")
    assert resp.status_code == 200
    # default list (include_inactive=True) ainda mostra, marcado inativo
    rows = client.get("/api/colaboradores").json()["colaboradores"]
    assert rows[0]["ativo"] is False
    # list só ativos -> vazio
    assert client.get("/api/colaboradores?include_inactive=false").json()["colaboradores"] == []


def test_hard_delete_rejeita_colaborador_ativo(client, as_admin):
    cid = client.post(
        "/api/colaboradores", json={"nome": "Ainda Ativo", "papel": "advogado"}
    ).json()["id"]
    resp = client.delete(f"/api/colaboradores/{cid}?hard=true")
    assert resp.status_code == 400
    # continua existindo
    assert any(c["id"] == cid for c in client.get("/api/colaboradores").json()["colaboradores"])


def test_hard_delete_apaga_colaborador_inativo(client, as_admin):
    cid = client.post(
        "/api/colaboradores", json={"nome": "Vai Sumir", "papel": "advogado"}
    ).json()["id"]
    client.delete(f"/api/colaboradores/{cid}")  # soft delete primeiro
    resp = client.delete(f"/api/colaboradores/{cid}?hard=true")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert not any(c["id"] == cid for c in client.get("/api/colaboradores").json()["colaboradores"])


def test_patch_404(client, as_admin):
    assert client.patch("/api/colaboradores/9999", json={"ativo": False}).status_code == 404


def test_delete_404(client, as_admin):
    assert client.delete("/api/colaboradores/9999").status_code == 404
