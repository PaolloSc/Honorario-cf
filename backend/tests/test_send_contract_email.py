"""Testa o encaminhamento do contrato por e-mail (POST /api/email/send).

O anexo é uma cópia de conferência enviada ao CLIENTE antes do DocuSeal, então
não pode conter as merge-tags de assinatura ({{...;type=signature;...}}) nem
usar o UUID cru como nome do arquivo.
"""
import sys
import uuid
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import ContractDB, ContractVersionDB, SessionLocal, utcnow
from app.main import app
from app.models.contract import ContratoRequest
from app.routers.email import get_email_service
from app.services.contract_generator import ContractGenerator

sys.path.insert(0, str(Path(__file__).parent))
from test_contract_generator_fidelidade import _base_req  # noqa: E402


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="advogado")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _seed_contract(client_name: str) -> str:
    contract_id = str(uuid.uuid4())
    _, filepath = ContractGenerator().generate(
        ContratoRequest(**_base_req()), contract_id=contract_id)
    db = SessionLocal()
    db.add(ContractDB(
        contract_id=contract_id, status="rascunho", client_name=client_name,
        client_email="cli@ex.com", current_version=1, created_by="lawyer@test.com",
        created_at=utcnow(), updated_at=utcnow()))
    db.add(ContractVersionDB(
        contract_id=contract_id, version_number=1, form_data_json="{}",
        file_path=filepath, created_at=utcnow()))
    db.commit()
    db.close()
    return contract_id


def _send(client, contract_id: str) -> dict:
    """Envia e captura os kwargs + o conteúdo do anexo DURANTE a chamada
    (o endpoint apaga a cópia temporária no finally)."""
    captured: dict = {}

    async def _capture(**kwargs):
        captured.update(kwargs)
        captured["attachment_bytes"] = Path(kwargs["attachment_path"]).read_bytes()
        return {"success": True, "message": "ok"}

    mock_service = MagicMock()
    mock_service.send_email_with_attachment = AsyncMock(side_effect=_capture)
    with patch("app.routers.email.get_email_service", return_value=mock_service):
        resp = client.post("/api/email/send", json={
            "contract_id": contract_id,
            "destinatario_email": "cli@ex.com",
            "destinatario_nome": "Fulano de Tal",
        })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    return captured


def test_anexo_nao_contem_tags_de_assinatura(client):
    import io

    contract_id = _seed_contract("Fulano de Tal")
    captured = _send(client, contract_id)

    xml = zipfile.ZipFile(io.BytesIO(captured["attachment_bytes"])).read(
        "word/document.xml").decode("utf-8")
    assert "type=signature" not in xml
    assert "{{Assinatura" not in xml
    assert "____" in xml  # linha de assinatura no lugar da tag


def test_nome_do_anexo_usa_nome_do_cliente_nao_uuid(client):
    contract_id = _seed_contract("Fulano de Tal")
    captured = _send(client, contract_id)

    assert "Fulano de Tal" in captured["attachment_name"]
    assert contract_id not in captured["attachment_name"]


def test_nome_do_anexo_sanitiza_caracteres_perigosos(client):
    # Qodo: client_name vem do usuario e pode ter controle/reservados de filesystem.
    contract_id = _seed_contract("Fulano/..\\Evil:\n\t Ltda*?")
    captured = _send(client, contract_id)

    name = captured["attachment_name"]
    assert name.endswith(".docx")
    for bad in '\r\n\t/\\:*?"<>|':
        assert bad not in name


def test_download_usa_nome_do_cliente(client):
    contract_id = _seed_contract("Fulano de Tal")
    resp = client.get(f"/api/contract/{contract_id}/download")
    assert resp.status_code == 200, resp.text
    cd = resp.headers["content-disposition"]
    assert "Fulano de Tal" in cd or "Fulano%20de%20Tal" in cd
    assert contract_id not in cd
