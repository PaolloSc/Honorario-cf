"""Previa do contrato de consumidor: renderiza antes de gravar, sem tocar no banco."""

from app.auth import CurrentUser, get_current_user
from app.database import ContractDB, ContractVersionDB, SessionLocal
from app.main import app
from tests.test_consumidor_generator import DOIS, PJ, UM


def _como_advogado():
    """Admin: o contrato de consumo e' restrito (ver test_consumidor_acesso.py)."""
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="admin"
    )


def _contagens() -> tuple[int, int]:
    db = SessionLocal()
    try:
        return db.query(ContractDB).count(), db.query(ContractVersionDB).count()
    finally:
        db.close()


def test_previa_renderiza_sem_gravar(client):
    antes = _contagens()
    _como_advogado()
    try:
        r = client.post("/api/contract/preview-consumidor", json=DOIS)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS" in r.text
    assert "CLÁUSULA I" in r.text
    assert "Os CONTRATANTES estão cientes" in r.text  # plural aplicado
    assert "R$ 40,00" in r.text  # milheiro da Azul
    # O ponto da previa: nada foi persistido.
    assert _contagens() == antes


def test_previa_aceita_pessoa_juridica(client):
    _como_advogado()
    try:
        r = client.post(
            "/api/contract/preview-consumidor", json={**UM, "contratantes": [PJ]}
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    assert "pessoa jurídica de direito privado" in r.text
    assert "neste ato representada por CARLOS SILVA" in r.text


def test_previa_recusa_dados_invalidos(client):
    _como_advogado()
    try:
        r = client.post("/api/contract/preview-consumidor", json={**UM, "contratantes": []})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 422
