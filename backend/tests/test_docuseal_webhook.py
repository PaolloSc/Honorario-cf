"""Webhook DocuSeal: ficha de participacao ao financeiro so quando todos assinam."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import AuditLogDB, ContractDB, ContractVersionDB, SessionLocal, utcnow

SECRET = "test-webhook-secret"

_FORM_COM_PARTICIPACAO = json.dumps({
    "contratantes": [{"tipo": "PF", "nome": "Cliente X", "email": "c@x.com"}],
    "escopos": [{"tipo": "consultoria_lgpd", "honorarios": ["pro_labore"]}],
    "participacao": {"tem_participacao": True, "percentual_ou_valor": "10%"},
})


def _seed(contract_id: str, submission_id: str):
    db = SessionLocal()
    try:
        db.add(ContractDB(
            contract_id=contract_id, status="enviado",
            client_name="Cliente X", client_email="c@x.com",
            current_version=1, created_by="lawyer@test.com",
            created_at=utcnow(), updated_at=utcnow(),
        ))
        db.commit()
        db.add(ContractVersionDB(
            contract_id=contract_id, version_number=1,
            form_data_json=_FORM_COM_PARTICIPACAO,
            docuseal_submission_id=submission_id,
            created_at=utcnow(),
        ))
        db.commit()
    finally:
        db.close()


def _mock_email():
    svc = MagicMock()
    svc.send_html_email = AsyncMock(return_value={"success": True})
    svc.send_html_email_with_attachment = AsyncMock(return_value={"success": True})
    return svc


def _audit_count(contract_id: str, action: str) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(AuditLogDB)
            .filter(AuditLogDB.contract_id == contract_id, AuditLogDB.action == action)
            .count()
        )
    finally:
        db.close()


def test_completed_sends_ficha_once_idempotent(client):
    _seed("wh-001", "sub-001")
    email = _mock_email()

    with patch("app.routers.docuseal.DOCUSEAL_WEBHOOK_SECRET", SECRET), \
         patch("app.routers.docuseal.get_email_service", return_value=email):
        body = {"event_type": "submission.completed", "data": {"id": "sub-001"}}
        headers = {"x-docuseal-secret": SECRET}
        r1 = client.post("/api/docuseal/webhook", json=body, headers=headers)
        r2 = client.post("/api/docuseal/webhook", json=body, headers=headers)

    assert r1.status_code == 200 and r2.status_code == 200
    # Ficha enviada exatamente 1x apesar de 2 entregas
    assert email.send_html_email.await_count == 1
    assert _audit_count("wh-001", "envio_participacao_final") == 1


def test_declined_does_not_send_ficha(client):
    _seed("wh-002", "sub-002")
    email = _mock_email()

    with patch("app.routers.docuseal.DOCUSEAL_WEBHOOK_SECRET", SECRET), \
         patch("app.routers.docuseal.get_email_service", return_value=email):
        body = {"event_type": "submission.declined", "data": {"id": "sub-002"}}
        r = client.post("/api/docuseal/webhook", json=body, headers={"x-docuseal-secret": SECRET})

    assert r.status_code == 200
    assert email.send_html_email.await_count == 0
    assert _audit_count("wh-002", "envio_participacao_final") == 0
