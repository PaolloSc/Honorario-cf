from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.nfse_db import NFSeRecebidaDB  # noqa: F401 -- load metadata


def test_registra_pagamento_e_vincula():
    from app.services.nfse_pagamento import gerar_pagamento_para_nfse

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    with Session() as db:
        part_id = _seed_contrato_participacao(db)
        db.execute(text("""
            INSERT INTO nfse_recebidas (cnpj_prestador, numero, competencia, data_emissao,
                                        tomador_doc, valor_servicos, valor_liquido,
                                        xml_raw, status_matching, contract_id, participacao_id)
            VALUES ('12345678000199', '1', '2026-05-01', '2026-05-10',
                    '98765432000100', 1000, 970, x'00', 'auto', 'c-1', :pid)
        """), {"pid": part_id})
        db.commit()
        nfse_id = db.execute(text("SELECT id FROM nfse_recebidas LIMIT 1")).scalar()

        result = gerar_pagamento_para_nfse(db, nfse_id=nfse_id)
        assert result.pagamento_id is not None

        row = db.execute(text("SELECT pagamento_id FROM nfse_recebidas WHERE id=:i"), {"i": nfse_id}).fetchone()
        assert row[0] == result.pagamento_id


def test_idempotente_nao_duplica():
    from app.services.nfse_pagamento import gerar_pagamento_para_nfse

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    with Session() as db:
        part_id = _seed_contrato_participacao(db)
        db.execute(text("""
            INSERT INTO nfse_recebidas (cnpj_prestador, numero, competencia, data_emissao,
                                        tomador_doc, valor_servicos, valor_liquido,
                                        xml_raw, status_matching, contract_id, participacao_id)
            VALUES ('12345678000199', '2', '2026-05-01', '2026-05-10',
                    '98765432000100', 500, 485, x'00', 'auto', 'c-1', :pid)
        """), {"pid": part_id})
        db.commit()
        nfse_id = db.execute(text("SELECT id FROM nfse_recebidas LIMIT 1")).scalar()

        r1 = gerar_pagamento_para_nfse(db, nfse_id=nfse_id)
        r2 = gerar_pagamento_para_nfse(db, nfse_id=nfse_id)
        assert r1.pagamento_id == r2.pagamento_id
        n_pagamentos = db.execute(text("SELECT COUNT(*) FROM participacao_pagamentos")).scalar()
        assert n_pagamentos == 1


def _seed_contrato_participacao(db):
    db.execute(text("""
        INSERT INTO contracts (contract_id, status, client_name, client_email,
                               current_version, cliente_docs, created_at, updated_at)
        VALUES ('c-1', 'ativo', 'X', 'x@x.com', 1, '["98765432000100"]', '2026-01-01', '2026-01-01')
    """))
    db.execute(text("""
        INSERT INTO participacoes (contract_id, beneficiario_email, beneficiario_nome,
                                   tipo_honorario, percentual_captacao, percentual_performance,
                                   natureza, cliente_cpf_cnpj, data_inicio, vinculo_ativo,
                                   aprovada, created_at, updated_at)
        VALUES ('c-1', 'b@x.com', 'B', 'mensalidade', 10, 0, 'contratual',
                '98765432000100', '2024-08-01', 1, 1, '2026-01-01', '2026-01-01')
    """))
    db.commit()
    return db.execute(text("SELECT id FROM participacoes WHERE contract_id='c-1'")).scalar()
