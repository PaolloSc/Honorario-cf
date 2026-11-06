"""Caso de uso Assinatura (services/assinatura.py), sem passar pela rota.

O seam e' o parametro `docuseal`: um falso entra direto, sem patch de nome de rota.
Aqui ficam as regras do envio que a Angela nao consegue testar no homolog (mandaria
convite a pessoas reais): quem assina, testemunha fixa, papeis unicos, ordem,
reenvio, auditoria e o que acontece quando o DocuSeal falha.
"""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.database import AuditLogDB, ColaboradorDB, ContractDB, ContractVersionDB, SessionLocal, utcnow
from app.services.arquivo_contrato import ArquivoNaoEncontrado, resolve_backend_path
from app.services.assinatura import EnvioInvalido, enviar

SOCIO = {"email": "socia-svc@cf.com", "name": "Socia", "role": "Contratado"}
CLIENTE = {"email": "cli-svc@ex.com", "name": "Cliente", "role": "Contratante"}


@pytest.fixture
def db():
    s = SessionLocal()
    s.add(ColaboradorDB(nome="Socia", email=SOCIO["email"], papel="socio", ativo=True))
    s.add(ColaboradorDB(nome="Adv", email="adv-svc@cf.com", papel="advogado", ativo=True))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def contrato(db):
    cid = str(uuid.uuid4())
    out = resolve_backend_path(settings.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    arquivo = out / f"contrato_{cid}.docx"
    arquivo.write_bytes(b"x")
    db.add(ContractDB(contract_id=cid, status="rascunho", client_name="Cliente SA", client_email="c@ex.com",
                      current_version=1, created_at=utcnow(), updated_at=utcnow()))
    db.add(ContractVersionDB(contract_id=cid, version_number=1, form_data_json="{}",
                             file_path=str(arquivo), created_at=utcnow()))
    db.commit()
    yield cid
    arquivo.unlink(missing_ok=True)


def _docuseal(submission_id=77, sucesso=True, submitters=None, template_id=1):
    d = MagicMock()
    d.create_template_from_docx = AsyncMock(return_value={"id": template_id} if template_id else {})
    d.send_for_signature = AsyncMock(return_value={
        "success": sucesso, "message": "recusado pelo DocuSeal",
        "submission": {"id": submission_id, "submitters": submitters or []},
    })
    d.archive_submission = AsyncMock(return_value=True)
    return d


def _enviar(db, cid, signatarios, docuseal):
    return asyncio.run(enviar(db, cid, [dict(s) for s in signatarios], "adv-svc@cf.com", docuseal=docuseal))


def test_envio_ok_marca_enviado_audita_e_devolve_contratantes(db, contrato):
    d = _docuseal(submitters=[{"role": "Contratante", "email": "cli-svc@ex.com"}, {"role": "Contratado"}])
    r = _enviar(db, contrato, [CLIENTE, SOCIO], d)

    assert r.success and r.submission_id == "77"
    assert [s["role"] for s in r.contratantes] == ["Contratante"]
    db.expire_all()
    c = db.query(ContractDB).filter_by(contract_id=contrato).one()
    assert c.status == "enviado"
    v = db.query(ContractVersionDB).filter_by(contract_id=contrato).one()
    assert v.docuseal_submission_id == "77"
    log = db.query(AuditLogDB).filter_by(contract_id=contrato, action="envio_assinatura").one()
    assert log.user_email == "adv-svc@cf.com"


def test_ordem_e_testemunha_fixa(db, contrato):
    d = _docuseal()
    _enviar(db, contrato, [SOCIO, CLIENTE], d)
    enviados = d.send_for_signature.await_args.kwargs["signatarios"]
    assert [s["role"] for s in enviados] == ["Contratante", "Contratado", "Testemunha"]
    assert enviados[-1]["email"].lower() == settings.testemunha1_email.lower()
    assert enviados[-1]["order"] == 5
    assert enviados[1]["contratado_nome"] == "Carvalho & Furtado Advogados"


def test_dois_contratantes_ganham_numero_no_papel(db, contrato):
    d = _docuseal()
    _enviar(db, contrato, [CLIENTE, {**CLIENTE, "email": "b@ex.com"}, SOCIO], d)
    papeis = [s["role"] for s in d.send_for_signature.await_args.kwargs["signatarios"]]
    assert "Contratante 1" in papeis and "Contratante 2" in papeis


def test_sem_socio_ou_com_nao_socio_recusa_e_nao_chama_docuseal(db, contrato):
    d = _docuseal()
    with pytest.raises(EnvioInvalido):
        _enviar(db, contrato, [CLIENTE], d)
    with pytest.raises(EnvioInvalido):
        _enviar(db, contrato, [CLIENTE, {**SOCIO, "email": "adv-svc@cf.com"}], d)
    d.create_template_from_docx.assert_not_awaited()
    db.expire_all()
    assert db.query(ContractDB).filter_by(contract_id=contrato).one().status == "rascunho"


def test_docuseal_recusa_nao_muda_status(db, contrato):
    r = _enviar(db, contrato, [CLIENTE, SOCIO], _docuseal(sucesso=False))
    assert not r.success and r.message == "recusado pelo DocuSeal"
    db.expire_all()
    assert db.query(ContractDB).filter_by(contract_id=contrato).one().status == "rascunho"
    assert db.query(AuditLogDB).filter_by(contract_id=contrato, action="envio_assinatura").count() == 0


def test_template_sem_id_devolve_falha_sem_enviar(db, contrato):
    d = _docuseal(template_id=None)
    r = _enviar(db, contrato, [CLIENTE, SOCIO], d)
    assert not r.success
    d.send_for_signature.assert_not_awaited()


def test_reenvio_arquiva_a_submissao_anterior(db, contrato):
    v = db.query(ContractVersionDB).filter_by(contract_id=contrato).one()
    v.docuseal_submission_id = "111"
    db.query(ContractDB).filter_by(contract_id=contrato).one().status = "enviado"
    db.commit()
    d = _docuseal(submission_id=222)
    _enviar(db, contrato, [CLIENTE, SOCIO], d)
    d.archive_submission.assert_awaited_once_with("111")


def test_falha_ao_arquivar_nao_impede_o_envio(db, contrato):
    v = db.query(ContractVersionDB).filter_by(contract_id=contrato).one()
    v.docuseal_submission_id = "111"
    db.query(ContractDB).filter_by(contract_id=contrato).one().status = "recusado"
    db.commit()
    d = _docuseal(submission_id=222)
    d.archive_submission = AsyncMock(side_effect=RuntimeError("fora do ar"))
    assert _enviar(db, contrato, [CLIENTE, SOCIO], d).success


def test_contrato_sem_arquivo_levanta_erro_de_dominio(db):
    cid = str(uuid.uuid4())
    db.add(ContractDB(contract_id=cid, status="rascunho", client_name="X", client_email="x@ex.com",
                      current_version=1, created_at=utcnow(), updated_at=utcnow()))
    db.add(ContractVersionDB(contract_id=cid, version_number=1, form_data_json="",
                             file_path="/nao/existe.docx", created_at=utcnow()))
    db.commit()
    with pytest.raises(ArquivoNaoEncontrado):
        _enviar(db, cid, [CLIENTE, SOCIO], _docuseal())
