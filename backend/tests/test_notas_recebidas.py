"""Acesso a dados das notas recebidas (ORM): vinculo manual, cancelamento, existencia e NSU."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, ContractDB, ParticipacaoDB
from app.models.nfse import NFSeData
from app.models.nfse_db import NFSeAuditLogDB, SyncJobDB
from app.services import notas_recebidas as notas


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with sessionmaker(bind=eng)() as s:
        s.add(ContractDB(contract_id="c-1", status="ativo", client_name="X", client_email="x@x.com",
                         current_version=1, cliente_docs='["98765432000100"]',
                         created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1)))
        s.commit()
        yield s


def _nf(**kw) -> NFSeData:
    base = dict(cnpj_prestador="12345678000199", numero="10", serie=None, competencia=date(2026, 5, 1),
                data_emissao=date(2026, 5, 2), tomador_doc="98765432000100", valor_servicos="100.00",
                xml_raw=b"<x/>")
    base.update(kw)
    return NFSeData(**base)


def _grava(db, nf, status="pendente"):
    n = notas.criar_nota(db, nf, contract_id=None, participacao_id=None, status=status, motivo=None)
    db.commit()
    return n


def test_existente_acha_serie_nula_e_distingue_direcao(db):
    n = _grava(db, _nf())
    assert notas.achar_existente(db, _nf()).id == n.id
    assert notas.achar_existente(db, _nf(direcao="recebida")) is None
    assert notas.achar_existente(db, _nf(serie="A")) is None


def test_cancelar_por_chave_so_uma_vez(db):
    chave = "1" * 50
    _grava(db, _nf(chave_acesso=chave))
    assert notas.cancelar_por_chave(db, chave, datetime.now(timezone.utc)) == 1
    db.commit()
    assert notas.cancelar_por_chave(db, chave, None) == 0  # ja cancelada
    assert notas.cancelar_por_chave(db, "2" * 50, None) == 0  # evento sem nota: sem efeito


def test_vincular_manual_grava_auditoria_e_recusa_casos_invalidos(db):
    n = _grava(db, _nf())
    db.add(ParticipacaoDB(contract_id="c-1", beneficiario_email="b@x.com", beneficiario_nome="B",
                          tipo_honorario="mensalidade", percentual_captacao=10, percentual_performance=0,
                          natureza="contratual", cliente_cpf_cnpj="98765432000100", data_inicio=date(2024, 8, 1),
                          vinculo_ativo=True, aprovada=True, created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1)))
    db.commit()

    with pytest.raises(notas.ContratoNaoExiste):
        notas.vincular_manual(db, n.id, "nao-existe", None, "a@x.com")
    with pytest.raises(notas.NotaNaoEncontrada):
        notas.vincular_manual(db, 999, "c-1", None, "a@x.com")

    nota, part = notas.vincular_manual(db, n.id, "c-1", "conferido", "a@x.com")
    assert nota.status_matching == "manual" and nota.contract_id == "c-1" and part is not None
    assert db.query(NFSeAuditLogDB).filter_by(nfse_id=n.id, acao="nfse.vincular_manual", user_email="a@x.com").count() == 1
    nota.status_matching = "auto"
    with pytest.raises(notas.NotaNaoVinculavel):
        notas.vincular_manual(db, n.id, "c-1", None, "a@x.com")


def test_ultimo_nsu_so_conta_jobs_ok(db):
    for status, nsu in (("ok", 40), ("erro", 99), ("ok", 70)):
        db.add(SyncJobDB(cnpj_prestador="12345678000199", origem="cron", iniciado_em=datetime.now(timezone.utc),
                         periodo_inicio=date(2026, 5, 1), periodo_fim=date(2026, 5, 31), status=status, ultimo_nsu=nsu))
    db.commit()
    assert notas.ultimo_nsu(db, "12345678000199") == 70
    assert notas.ultimo_nsu(db, "00000000000000") == 0
