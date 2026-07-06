def test_download_invalid_uuid(client):
    """Path traversal attempt should be rejected."""
    response = client.get("/api/contract/../../etc/passwd/download")
    assert response.status_code in (400, 401, 404, 422)


def test_download_nonexistent_contract(client):
    """Valid UUID but nonexistent contract should return 401 or 404."""
    response = client.get("/api/contract/00000000-0000-0000-0000-000000000000/download")
    assert response.status_code in (401, 404)


def test_preview_invalid_uuid(client):
    response = client.get("/api/contract/../../etc/passwd/preview")
    assert response.status_code in (400, 401, 404, 422)


def test_preview_nonexistent_contract(client):
    response = client.get("/api/contract/00000000-0000-0000-0000-000000000000/preview")
    assert response.status_code in (401, 404)


def test_preview_returns_html_for_owned_contract(client):
    import json
    import uuid

    from app.auth import CurrentUser, get_current_user
    from app.database import ContractDB, ContractVersionDB, SessionLocal, utcnow
    from app.main import app
    from app.models.contract import ContratoRequest
    from app.services.contract_generator import ContractGenerator

    form_data = {
        "contratantes": [{
            "tipo": "PF", "nome": "Fulano", "nacionalidade": "brasileiro",
            "cpf": "00000000000", "profissao": "x", "estado_civil": "Solteiro(a)",
            "endereco": "rua x", "email": "a@a.com",
        }],
        "escopos": [{"tipo": "consultoria_lgpd", "honorarios": ["pro_labore"],
                     "pro_labore": {"valor_total": 10000, "tem_parcelamento": False}}],
        "acessorios": {"tem_reembolso": True, "reembolso_limitado": False,
                       "tem_penalidade_inadimplemento": False},
        "participacao": {"tem_participacao": False},
    }
    contract_id = str(uuid.uuid4())
    _, filepath = ContractGenerator().generate(ContratoRequest(**form_data), contract_id=contract_id)

    db = SessionLocal()
    db.add(ContractDB(
        contract_id=contract_id, status="rascunho", client_name="Fulano",
        client_email="a@a.com", current_version=1, created_by="lawyer@test.com",
        created_at=utcnow(), updated_at=utcnow(),
    ))
    db.add(ContractVersionDB(
        contract_id=contract_id, version_number=1,
        form_data_json=json.dumps(form_data), file_path=filepath, created_at=utcnow(),
    ))
    db.commit()
    db.close()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="advogado")
    try:
        response = client.get(f"/api/contract/{contract_id}/preview")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS" in response.text
