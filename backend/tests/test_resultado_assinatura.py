"""Resultado da assinatura: a ficha ao financeiro sai uma vez so', mesmo com webhook e sincronizacao juntos."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.database import AuditLogDB, ContractDB, ContractVersionDB, SessionLocal, utcnow
from app.services import resultado_assinatura

_FORM = json.dumps({
    "escopos": [{"tipo": "consultoria_lgpd"}],
    "participacao": {"tem_participacao": True, "percentual_ou_valor": "10%"},
})


def _seed(cid: str):
    db = SessionLocal()
    try:
        db.add(ContractDB(contract_id=cid, status="enviado", client_name="Cliente <b>X</b>",
                          client_email="c@x.com", current_version=1, created_by="adv@test.com",
                          created_at=utcnow(), updated_at=utcnow()))
        db.commit()
        db.add(ContractVersionDB(contract_id=cid, version_number=1, form_data_json=_FORM,
                                 docuseal_submission_id=f"sub-{cid}", created_at=utcnow()))
        db.commit()
    finally:
        db.close()


def _email_lento():
    async def lento(**kw):
        await asyncio.sleep(0.05)  # a chamada ao e-mail cede o controle: o outro caminho entra
        return {"success": True}
    svc = MagicMock()
    svc.send_html_email = AsyncMock(side_effect=lento)
    return svc


def test_erro_c_webhook_e_sincronizacao_juntos_mandam_uma_ficha(client):
    _seed("rc-001")
    svc = _email_lento()

    async def caminho(acao):
        db = SessionLocal()
        try:
            c = db.query(ContractDB).filter(ContractDB.contract_id == "rc-001").first()
            v = db.query(ContractVersionDB).filter(ContractVersionDB.contract_id == "rc-001").first()
            await resultado_assinatura.aplicar_conclusao(c, v, "assinado", acao, "teste", db)
        finally:
            db.close()

    async def ambos():
        await asyncio.gather(caminho("webhook_assinado"), caminho("sync_assinado"))

    with patch("app.services.servicos_externos.get_email_service", return_value=svc):
        asyncio.run(ambos())

    assert svc.send_html_email.await_count == 1
    db = SessionLocal()
    try:
        n = db.query(AuditLogDB).filter(AuditLogDB.contract_id == "rc-001",
                                        AuditLogDB.action == "envio_participacao_final").count()
    finally:
        db.close()
    assert n == 1


def _roda(cid, svc):
    async def go():
        db = SessionLocal()
        try:
            c = db.query(ContractDB).filter(ContractDB.contract_id == cid).first()
            v = db.query(ContractVersionDB).filter(ContractVersionDB.contract_id == cid).first()
            await resultado_assinatura.aplicar_conclusao(c, v, "assinado", "sync_assinado", "t", db)
        finally:
            db.close()
    with patch("app.services.servicos_externos.get_email_service", return_value=svc):
        asyncio.run(go())


def test_ficha_escapa_nome_do_cliente(client):
    _seed("rc-002")
    svc = MagicMock()
    svc.send_html_email = AsyncMock(return_value={"success": True})
    _roda("rc-002", svc)
    html = svc.send_html_email.await_args.kwargs["html_content"]
    assert "<b>X</b>" not in html and "&lt;b&gt;X&lt;/b&gt;" in html


def test_ficha_com_falha_no_envio_tenta_de_novo_na_proxima(client):
    _seed("rc-003")
    ruim = MagicMock()
    ruim.send_html_email = AsyncMock(return_value={"success": False, "error": "x"})
    _roda("rc-003", ruim)
    bom = MagicMock()
    bom.send_html_email = AsyncMock(return_value={"success": True})
    _roda("rc-003", bom)
    assert bom.send_html_email.await_count == 1


def test_ficha_final_sem_participacao_sai_dizendo_sem_participacao(client):
    cid = "rc-004"
    db = SessionLocal()
    try:
        db.add(ContractDB(contract_id=cid, status="enviado", client_name="Cliente Y", client_email="c@x.com",
                          current_version=1, created_by="adv@test.com", created_at=utcnow(), updated_at=utcnow()))
        db.commit()
        db.add(ContractVersionDB(
            contract_id=cid, version_number=1, docuseal_submission_id="s", created_at=utcnow(),
            form_data_json=json.dumps({"escopos": [{"tipo": "consultoria_lgpd"}],
                                       "participacao": {"tem_participacao": False, "valor_percentual": "9",
                                                        "valor_tipo": "percentual", "responsavel_gestao": "Carla"}})))
        db.commit()
    finally:
        db.close()
    svc = MagicMock()
    svc.send_html_email = AsyncMock(return_value={"success": True})
    _roda(cid, svc)
    html = svc.send_html_email.await_args.kwargs["html_content"]
    assert "Sem participação" in html and "Carla" in html and "9%" not in html
