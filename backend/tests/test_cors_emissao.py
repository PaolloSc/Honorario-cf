"""O navegador manda preflight (OPTIONS) antes do POST de emitir, que leva o cabecalho Idempotency-Key."""
from fastapi.testclient import TestClient

from app.main import app


def _preflight(cabecalhos: str):
    return TestClient(app).options(
        "/api/faturas/1/emitir",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": cabecalhos,
        },
    )


def test_preflight_do_emitir_aceita_idempotency_key():
    r = _preflight("authorization,idempotency-key")
    assert r.status_code == 200
    permitidos = r.headers["access-control-allow-headers"].lower()
    assert "idempotency-key" in permitidos and "authorization" in permitidos
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_preflight_continua_recusando_cabecalho_desconhecido():
    assert _preflight("x-qualquer-coisa").status_code == 400
