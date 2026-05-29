"""GET /api/users/colaboradores: lista colaboradores p/ qualquer usuario logado."""
from types import SimpleNamespace

from app.main import app
from app.auth import get_current_user
from app.database import UserDB, get_db


def _seed_users(client):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.add(UserDB(azure_id="z1", email="bruno@cf.com", name="Bruno Advogado", role="advogado"))
        db.add(UserDB(azure_id="a1", email="ana@cf.com", name="Ana Admin", role="admin"))
        db.commit()
    finally:
        db.close()


def test_colaboradores_requires_auth(client):
    resp = client.get("/api/users/colaboradores")
    assert resp.status_code in (401, 403)


def test_colaboradores_lists_all_sorted_by_name(client):
    _seed_users(client)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        azure_id="x", email="x@x.com", name="X", role="advogado"
    )
    try:
        resp = client.get("/api/users/colaboradores")
        assert resp.status_code == 200
        data = resp.json()
        nomes = [c["name"] for c in data["colaboradores"]]
        assert nomes == ["Ana Admin", "Bruno Advogado"]
        assert data["colaboradores"][0]["email"] == "ana@cf.com"
        assert data["colaboradores"][0]["role"] == "admin"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
