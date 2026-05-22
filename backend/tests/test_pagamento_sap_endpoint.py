from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import pytest

from app.main import app
from app.database import Base, ContractDB, engine, SessionLocal, ParticipacaoDB, TaxCodeDB


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
    Base.metadata.drop_all(bind=engine)


def _client():
    c = TestClient(app)
    c.headers["X-Dev-User-Email"] = "fin@test.local"
    c.headers["X-Dev-User-Role"] = "financeiro"
    return c


def _criar_participacao() -> int:
    with SessionLocal() as s:
        if not s.query(ContractDB).filter(ContractDB.contract_id == "test-contract-sap").first():
            s.add(ContractDB(contract_id="test-contract-sap", status="ativo", client_name="X", client_email="x@x.com"))
            s.commit()
        p = ParticipacaoDB(
            contract_id="test-contract-sap",
            beneficiario_email="adv@x.com",
            beneficiario_nome="Adv",
            tipo_honorario="hora",
            percentual_captacao=10.0,
            percentual_performance=0.0,
            natureza="contratual",
            data_inicio=date(2024, 8, 1),
            vinculo_ativo=True,
            aprovada=True,
            created_by="seed",
        )
        s.add(p)
        s.commit()
        return p.id


def test_registra_pagamento_calcula_componentes_sap():
    pid = _criar_participacao()
    c = _client()
    r = c.post(f"/api/participacoes/{pid}/pagamentos", json={
        "data_recebimento": "2026-05-01",
        "valor_bruto": 10000.0,
        "discriminado": True,
        "tipo_documento": "nf",
        "nf_referencia": "NF2026.999",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valor_bruto"] == 10000.0
    assert body["imposto_total"] == 1545.0
    assert body["valor_liquido_recebido"] == 8455.0
    assert body["valor_participacao"] == 845.5
    assert body["tax_code_codigo"] == "PADRAO_1545"
    assert body["aliquota_aplicada"] == 0.1545


def test_tipo_documento_invalido_422():
    pid = _criar_participacao()
    c = _client()
    r = c.post(f"/api/participacoes/{pid}/pagamentos", json={
        "data_recebimento": "2026-05-01",
        "valor_bruto": 1000.0,
        "tipo_documento": "xyz",
    })
    assert r.status_code == 422


def test_natureza_pagamento_invalida_422():
    pid = _criar_participacao()
    c = _client()
    r = c.post(f"/api/participacoes/{pid}/pagamentos", json={
        "data_recebimento": "2026-05-01",
        "valor_bruto": 1000.0,
        "natureza_pagamento": "nao_existe",
    })
    assert r.status_code == 422


def test_tax_code_desativado_422():
    pid = _criar_participacao()
    c = _client()
    r0 = c.post("/api/tax-codes", json={
        "codigo": "TMP_DESATIVAR", "descricao": "x", "aliquota_total": 0.10,
        "aliquota_iss": 0, "aliquota_pis": 0, "aliquota_cofins": 0,
        "aliquota_irrf": 0, "aliquota_csll": 0,
    })
    tid = r0.json()["id"]
    c.post(f"/api/tax-codes/{tid}/desativar")
    r = c.post(f"/api/participacoes/{pid}/pagamentos", json={
        "data_recebimento": "2026-05-01",
        "valor_bruto": 1000.0,
        "tax_code_id": tid,
    })
    assert r.status_code == 422
