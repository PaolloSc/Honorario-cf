"""GET /api/users/colaboradores: lista colaboradores (roster) p/ usuario logado."""
from types import SimpleNamespace

from app.main import app
from app.auth import get_current_user
from app.database import ColaboradorDB, SessionLocal


def _seed_roster():
    db = SessionLocal()
    try:
        db.add(ColaboradorDB(nome="Bruno Advogado", email="bruno@cf.com", papel="advogado", ordem=2))
        db.add(ColaboradorDB(nome="Ana Socia", email="ana@cf.com", papel="socio", ordem=1))
        db.add(ColaboradorDB(nome="Carla Estagiaria", email="carla@cf.com", papel="estagiario", ordem=3))
        db.add(ColaboradorDB(nome="Dario Inativo", email="dario@cf.com", papel="advogado", ativo=False, ordem=4))
        db.commit()
    finally:
        db.close()


def test_colaboradores_requires_auth(client):
    resp = client.get("/api/users/colaboradores")
    assert resp.status_code in (401, 403)


def _override_user(role="advogado"):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        azure_id="x", email="x@x.com", name="X", role=role
    )


def test_colaboradores_lists_active_sorted_by_ordem(client):
    _seed_roster()
    _override_user()
    try:
        resp = client.get("/api/users/colaboradores")
        assert resp.status_code == 200
        nomes = [c["name"] for c in resp.json()["colaboradores"]]
        # ativos ordenados por ordem: Ana(1), Bruno(2), Carla(3) — Dario inativo fora
        assert nomes == ["Ana Socia", "Bruno Advogado", "Carla Estagiaria"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_colaboradores_participavel_filter(client):
    _seed_roster()
    _override_user()
    try:
        resp = client.get("/api/users/colaboradores?participavel=true")
        assert resp.status_code == 200
        nomes = [c["name"] for c in resp.json()["colaboradores"]]
        # so advogados/socios ativos: Ana(socio), Bruno(advogado)
        assert nomes == ["Ana Socia", "Bruno Advogado"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_colaboradores_include_inactive(client):
    _seed_roster()
    _override_user()
    try:
        resp = client.get("/api/users/colaboradores?include_inactive=true")
        nomes = [c["name"] for c in resp.json()["colaboradores"]]
        assert "Dario Inativo" in nomes
    finally:
        app.dependency_overrides.pop(get_current_user, None)
