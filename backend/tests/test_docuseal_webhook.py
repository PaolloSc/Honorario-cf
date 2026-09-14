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


# ── Sincronizacao ativa: contrato preso em "enviado" ─────────────────────
#
# O webhook depende de duas pontas externas (DOCUSEAL_WEBHOOK_SECRET no backend
# e o webhook cadastrado no DocuSeal). Faltando qualquer uma, o contrato ficava
# em "enviado" para sempre mesmo com todas as assinaturas colhidas.

from types import SimpleNamespace  # noqa: E402

from app.auth import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import docuseal as docuseal_mod  # noqa: E402


def _status_do_contrato(contract_id: str) -> str:
    db = SessionLocal()
    try:
        return db.query(ContractDB).filter(
            ContractDB.contract_id == contract_id
        ).first().status
    finally:
        db.close()


@pytest.fixture
def usuario_logado():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        azure_id="dev::adv", email="lawyer@test.com", name="Adv", role="advogado",
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _mock_docuseal(status_data: dict):
    svc = MagicMock()
    svc.get_submission_status = AsyncMock(return_value=status_data)
    return svc


@pytest.mark.parametrize("status_data", [
    # O formato variou entre versoes do DocuSeal: os tres sinais valem.
    {"status": "completed", "submitters": []},
    {"completed_at": "2026-09-14T12:00:00Z", "submitters": []},
    {"submitters": [
        {"role": "Contratante", "completed_at": "2026-09-14T11:00:00Z"},
        {"role": "Advogado", "completed_at": "2026-09-14T11:30:00Z"},
        {"role": "Contratado", "completed_at": "2026-09-14T12:00:00Z"},
    ]},
])
def test_sincronizar_conclui_contrato_travado_em_enviado(client, usuario_logado, status_data):
    cid = f"sync-{abs(hash(str(status_data))) % 10**6}"
    _seed(cid, f"sub-{cid}")
    email = _mock_email()

    with patch.object(docuseal_mod, "get_docuseal_service", return_value=_mock_docuseal(status_data)), \
         patch.object(docuseal_mod, "get_email_service", return_value=email):
        r = client.post(f"/api/docuseal/{cid}/sincronizar")

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "assinado"
    assert r.json()["alterado"] is True
    assert _status_do_contrato(cid) == "assinado"
    # A ficha ao financeiro sai por este caminho tambem, nao so' pelo webhook.
    assert email.send_html_email.await_count == 1


def test_sincronizar_nao_conclui_com_assinatura_pendente(client, usuario_logado):
    _seed("sync-pend", "sub-sync-pend")
    email = _mock_email()
    pendente = {"submitters": [
        {"role": "Contratante", "name": "Cliente X", "email": "c@x.com", "completed_at": "2026-09-14T11:00:00Z"},
        {"role": "Contratado", "name": "Carvalho & Furtado Advogados", "email": "contrato@x.com", "completed_at": None},
    ]}

    with patch.object(docuseal_mod, "get_docuseal_service", return_value=_mock_docuseal(pendente)), \
         patch.object(docuseal_mod, "get_email_service", return_value=email):
        r = client.post("/api/docuseal/sync-pend/sincronizar")

    assert r.status_code == 200
    body = r.json()
    assert body["alterado"] is False
    assert _status_do_contrato("sync-pend") == "enviado"
    assert email.send_html_email.await_count == 0
    # Quem assinou nao aparece; so quem falta, pra mostrar na tela do contrato.
    assert body["pendentes"] == [
        {"role": "Contratado", "name": "Carvalho & Furtado Advogados", "email": "contrato@x.com"}
    ]
    assert "Carvalho & Furtado Advogados" in body["detalhe"]


def test_sincronizar_registra_recusa(client, usuario_logado):
    _seed("sync-rec", "sub-sync-rec")
    email = _mock_email()
    recusado = {"submitters": [{"role": "Contratante", "declined_at": "2026-09-14T11:00:00Z"}]}

    with patch.object(docuseal_mod, "get_docuseal_service", return_value=_mock_docuseal(recusado)), \
         patch.object(docuseal_mod, "get_email_service", return_value=email):
        r = client.post("/api/docuseal/sync-rec/sincronizar")

    assert r.status_code == 200
    assert _status_do_contrato("sync-rec") == "recusado"
    assert email.send_html_email.await_count == 0


def test_sincronizar_e_idempotente(client, usuario_logado):
    _seed("sync-idem", "sub-sync-idem")
    email = _mock_email()
    concluido = {"status": "completed", "submitters": []}

    with patch.object(docuseal_mod, "get_docuseal_service", return_value=_mock_docuseal(concluido)), \
         patch.object(docuseal_mod, "get_email_service", return_value=email):
        client.post("/api/docuseal/sync-idem/sincronizar")
        r2 = client.post("/api/docuseal/sync-idem/sincronizar")

    assert r2.json()["alterado"] is False
    assert email.send_html_email.await_count == 1
    assert _audit_count("sync-idem", "envio_participacao_final") == 1
    assert _audit_count("sync-idem", "sync_assinado") == 1
