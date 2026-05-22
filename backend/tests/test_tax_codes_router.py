from datetime import datetime, timezone

from fastapi.testclient import TestClient

import pytest

from app.main import app
from app.database import Base, engine, SessionLocal, TaxCodeDB


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    # seed PADRAO_1545
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
    Base.metadata.drop_all(bind=engine)


def _client_with_dev_user():
    c = TestClient(app)
    c.headers["X-Dev-User-Email"] = "financeiro@test.local"
    c.headers["X-Dev-User-Role"] = "financeiro"
    return c


def test_lista_tax_codes_inclui_padrao():
    c = _client_with_dev_user()
    r = c.get("/api/tax-codes")
    assert r.status_code == 200
    codigos = {tc["codigo"] for tc in r.json()}
    assert "PADRAO_1545" in codigos


def test_default_retorna_padrao():
    c = _client_with_dev_user()
    r = c.get("/api/tax-codes/default")
    assert r.status_code == 200
    assert r.json()["codigo"] == "PADRAO_1545"
    assert r.json()["aliquota_total"] == 0.1545


def test_cria_tax_code():
    c = _client_with_dev_user()
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
    c = _client_with_dev_user()
    payload = {
        "codigo": "DUP", "descricao": "x", "aliquota_total": 0,
        "aliquota_iss": 0, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    }
    c.post("/api/tax-codes", json=payload)
    r = c.post("/api/tax-codes", json=payload)
    assert r.status_code == 409


def test_patch_aliquota():
    c = _client_with_dev_user()
    r0 = c.post("/api/tax-codes", json={
        "codigo": "TEMP", "descricao": "tmp", "aliquota_total": 0.10,
        "aliquota_iss": 0.10, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    })
    tid = r0.json()["id"]
    r = c.patch(f"/api/tax-codes/{tid}", json={"aliquota_total": 0.05})
    assert r.status_code == 200
    assert r.json()["aliquota_total"] == 0.05


def test_desativar_padrao_falha_quando_unico_ativo():
    c = _client_with_dev_user()
    with SessionLocal() as s:
        padrao = s.query(TaxCodeDB).filter(TaxCodeDB.codigo == "PADRAO_1545").first()
        pid = padrao.id
    r = c.post(f"/api/tax-codes/{pid}/desativar")
    assert r.status_code == 422


def test_role_advogado_bloqueado():
    c = TestClient(app)
    c.headers["X-Dev-User-Email"] = "adv@test.local"
    c.headers["X-Dev-User-Role"] = "advogado"
    r = c.get("/api/tax-codes")
    assert r.status_code == 403
