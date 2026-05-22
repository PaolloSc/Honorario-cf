from datetime import datetime, timezone

from fastapi.testclient import TestClient

import pytest

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.database import Base, engine, SessionLocal, TaxCodeDB


def _fake_financeiro():
    return CurrentUser(
        azure_id="test-fin", email="financeiro@test.local", name="Fin", role="financeiro"
    )


def _fake_advogado():
    return CurrentUser(
        azure_id="test-adv", email="adv@test.local", name="Adv", role="advogado"
    )


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as s:
        if not s.query(TaxCodeDB).filter(TaxCodeDB.codigo == "PADRAO_1545").first():
            s.add(
                TaxCodeDB(
                    codigo="PADRAO_1545",
                    descricao="Retencoes agregadas",
                    aliquota_total=0.1545,
                    aliquota_iss=0,
                    aliquota_pis=0.0065,
                    aliquota_cofins=0.03,
                    aliquota_irrf=0.015,
                    aliquota_csll=0.01,
                    ativo=True,
                    criado_em=datetime.now(timezone.utc),
                    criado_por="sistema",
                )
            )
            s.commit()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    Base.metadata.drop_all(bind=engine)


def _client_financeiro():
    app.dependency_overrides[get_current_user] = _fake_financeiro
    return TestClient(app)


def test_lista_tax_codes_inclui_padrao():
    c = _client_financeiro()
    r = c.get("/api/tax-codes")
    assert r.status_code == 200
    codigos = {tc["codigo"] for tc in r.json()}
    assert "PADRAO_1545" in codigos


def test_default_retorna_padrao():
    c = _client_financeiro()
    r = c.get("/api/tax-codes/default")
    assert r.status_code == 200
    assert r.json()["codigo"] == "PADRAO_1545"
    assert r.json()["aliquota_total"] == 0.1545


def test_cria_tax_code():
    c = _client_financeiro()
    r = c.post("/api/tax-codes", json={
        "codigo": "isento",
        "descricao": "Sem retencao",
        "aliquota_total": 0,
        "aliquota_iss": 0, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["codigo"] == "ISENTO"
    assert body["ativo"] is True


def test_cria_duplicado_falha():
    c = _client_financeiro()
    payload = {
        "codigo": "DUP", "descricao": "x", "aliquota_total": 0,
        "aliquota_iss": 0, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    }
    c.post("/api/tax-codes", json=payload)
    r = c.post("/api/tax-codes", json=payload)
    assert r.status_code == 409


def test_patch_aliquota():
    c = _client_financeiro()
    r0 = c.post("/api/tax-codes", json={
        "codigo": "TEMP", "descricao": "tmp", "aliquota_total": 0.10,
        "aliquota_iss": 0.10, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    })
    assert r0.status_code == 201, r0.text
    tid = r0.json()["id"]
    r = c.patch(f"/api/tax-codes/{tid}", json={"aliquota_total": 0.05})
    assert r.status_code == 200
    assert r.json()["aliquota_total"] == 0.05


def test_desativar_padrao_falha_quando_unico_ativo():
    c = _client_financeiro()
    with SessionLocal() as s:
        padrao = s.query(TaxCodeDB).filter(TaxCodeDB.codigo == "PADRAO_1545").first()
        pid = padrao.id
    r = c.post(f"/api/tax-codes/{pid}/desativar")
    assert r.status_code == 422


def test_role_advogado_bloqueado():
    app.dependency_overrides[get_current_user] = _fake_advogado
    c = TestClient(app)
    r = c.get("/api/tax-codes")
    assert r.status_code == 403
