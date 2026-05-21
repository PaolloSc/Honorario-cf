from datetime import date
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.nfse_db import NFSeRecebidaDB  # noqa: F401 -- ensures metadata loaded


FIXTURES = Path(__file__).parent / "fixtures" / "nfse"


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    with Session() as s:
        s.execute(text("""
            INSERT INTO contracts (contract_id, status, client_name, client_email,
                                   current_version, cliente_docs, created_at, updated_at)
            VALUES ('c-1', 'ativo', 'X', 'x@x.com', 1, '["98765432000100"]', '2026-01-01', '2026-01-01')
        """))
        s.execute(text("""
            INSERT INTO participacoes (contract_id, beneficiario_email, beneficiario_nome,
                                       tipo_honorario, percentual_captacao, percentual_performance,
                                       natureza, cliente_cpf_cnpj, data_inicio, vinculo_ativo,
                                       aprovada, created_at, updated_at)
            VALUES ('c-1', 'b@x.com', 'B', 'mensalidade', 10, 0, 'contratual',
                    '98765432000100', '2024-08-01', 1, 1, '2026-01-01', '2026-01-01')
        """))
        s.commit()
        yield s


def test_ingest_uma_nf_auto_vinculada(db):
    from app.services.nfse_sync import ingest_payload

    xml = (FIXTURES / "abrasf_minimo.xml").read_bytes()
    job = ingest_payload(
        db,
        cnpj_prestador="12345678000199",
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
        origem="manual",
        disparado_por="teste@x",
        xmls=[xml],
    )
    assert job.status == "ok"
    assert job.total_nfs == 1
    assert job.auto_vinculadas == 1
    assert job.pendentes == 0
    nf = db.execute(text("SELECT status_matching, contract_id, pagamento_id FROM nfse_recebidas")).fetchone()
    assert nf[0] == "auto"
    assert nf[1] == "c-1"
    assert nf[2] is not None


def test_idempotencia_segunda_chamada_nao_duplica(db):
    from app.services.nfse_sync import ingest_payload

    xml = (FIXTURES / "abrasf_minimo.xml").read_bytes()
    ingest_payload(
        db,
        cnpj_prestador="12345678000199",
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
        origem="cron",
        disparado_por=None,
        xmls=[xml],
    )
    ingest_payload(
        db,
        cnpj_prestador="12345678000199",
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
        origem="cron",
        disparado_por=None,
        xmls=[xml],
    )
    n = db.execute(text("SELECT COUNT(*) FROM nfse_recebidas")).scalar()
    assert n == 1
    n_pag = db.execute(text("SELECT COUNT(*) FROM participacao_pagamentos")).scalar()
    assert n_pag == 1


def test_xml_malformado_conta_como_erro(db):
    from app.services.nfse_sync import ingest_payload

    job = ingest_payload(
        db,
        cnpj_prestador="12345678000199",
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
        origem="manual",
        disparado_por=None,
        xmls=[b"<not><valid"],
    )
    assert job.erros == 1
    assert job.total_nfs == 0


def test_cancelamento_detectado(db):
    from app.services.nfse_sync import ingest_payload

    xml = (FIXTURES / "abrasf_cancelada.xml").read_bytes()
    job = ingest_payload(
        db,
        cnpj_prestador="12345678000199",
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
        origem="manual",
        disparado_por=None,
        xmls=[xml],
    )
    assert job.total_nfs == 1
    row = db.execute(text("SELECT cancelada, status_matching FROM nfse_recebidas")).fetchone()
    assert row[0] == 1
    assert row[1] == "cancelada"


def test_lock_concorrente_segunda_chamada_e_no_op(db):
    """2 chamadas paralelas mesma janela: 2a retorna ja_rodando."""
    from app.services.nfse_sync import JobLockError, ingest_payload

    db.execute(text("""
        INSERT INTO sync_jobs (cnpj_prestador, origem, iniciado_em,
                               periodo_inicio, periodo_fim, status)
        VALUES ('12345678000199', 'cron', :n, '2026-05-01', '2026-05-31', 'em_andamento')
    """), {"n": datetime.now(timezone.utc)})
    db.commit()

    with pytest.raises(JobLockError):
        ingest_payload(
            db,
            cnpj_prestador="12345678000199",
            periodo_inicio=date(2026, 5, 1),
            periodo_fim=date(2026, 5, 31),
            origem="cron",
            disparado_por=None,
            xmls=[],
        )
