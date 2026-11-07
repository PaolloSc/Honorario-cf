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


def _nfse(db, part_id, numero, bruto, liquido, emissao):
    db.execute(text("""
        INSERT INTO nfse_recebidas (cnpj_prestador, numero, competencia, data_emissao,
                                    tomador_doc, valor_servicos, valor_liquido,
                                    xml_raw, status_matching, contract_id, participacao_id)
        VALUES ('12345678000199', :n, '2026-05-01', :e, '98765432000100', :b, :l,
                x'00', 'auto', 'c-1', :pid)
    """), {"n": numero, "e": emissao, "b": bruto, "l": liquido, "pid": part_id})
    db.commit()
    return db.execute(text("SELECT id FROM nfse_recebidas WHERE numero=:n"), {"n": numero}).scalar()


def _db_com_tax_code():
    from app.database import TaxCodeDB

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    db.add(TaxCodeDB(codigo="PADRAO_1545", descricao="padrao", aliquota_total="0.1545",
                     ativo=True, criado_por="t"))
    db.commit()
    return db


def test_nfse_e_manual_dao_o_mesmo_valor():
    """Mesmo recebimento (mesma data, bruto e participacao) por NFS-e e a mao."""
    from datetime import date
    from decimal import Decimal

    from app.database import ParticipacaoDB
    from app.services.nfse_pagamento import gerar_pagamento_para_nfse
    from app.services.pagamento_participacao import Recebimento, registrar

    db = _db_com_tax_code()
    part_id = _seed_contrato_participacao(db)
    nfse_id = _nfse(db, part_id, "9", 10000, 8455, "2026-05-10")
    via_nfse = db.get(__import__("app.database", fromlist=["x"]).ParticipacaoPagamentoDB,
                      gerar_pagamento_para_nfse(db, nfse_id).pagamento_id)
    via_mao = registrar(db, db.get(ParticipacaoDB, part_id),
                        Recebimento(data_recebimento=date(2026, 5, 10), valor_bruto=Decimal("10000")),
                        registrado_por="x@x.com")
    for campo in ("valor_bruto", "imposto_total", "valor_liquido_recebido",
                  "valor_participacao", "dentro_limite_temporal", "tax_code_id"):
        assert getattr(via_nfse, campo) == getattr(via_mao, campo), campo
    assert via_nfse.valor_participacao == Decimal("845.50")  # 10% de 8.455,00
    assert via_nfse.valor_bruto == Decimal("10000.00") and via_nfse.tax_code_id is not None


def test_nfse_aplica_regras_do_manual():
    from datetime import date

    db = _db_com_tax_code()
    part_id = _seed_contrato_participacao(db)  # mensalidade desde 2024-08-01: limite 2 anos
    from app.services.nfse_pagamento import gerar_pagamento_para_nfse
    from app.database import ParticipacaoPagamentoDB

    # depois do limite temporal de 2 anos: registra com participacao zerada e o motivo
    fora = _nfse(db, part_id, "10", 1000, 845.5, "2027-01-10")
    pag = db.get(ParticipacaoPagamentoDB, gerar_pagamento_para_nfse(db, fora).pagamento_id)
    assert pag.valor_participacao == 0 and pag.dentro_limite_temporal is False
    assert "Limite temporal" in pag.observacoes

    # antes do corte de 31/07/2024: nao retroativo
    antes = _nfse(db, part_id, "11", 1000, 845.5, "2024-07-31")
    pag = db.get(ParticipacaoPagamentoDB, gerar_pagamento_para_nfse(db, antes).pagamento_id)
    assert pag.valor_participacao == 0 and "31/07/2024" in pag.observacoes

    # vinculo encerrado: tambem zera
    db.execute(text("UPDATE participacoes SET vinculo_ativo = 0"))
    db.commit()
    enc = _nfse(db, part_id, "12", 1000, 845.5, "2026-05-10")
    pag = db.get(ParticipacaoPagamentoDB, gerar_pagamento_para_nfse(db, enc).pagamento_id)
    assert pag.valor_participacao == 0 and "Vínculo encerrado" in pag.observacoes
    assert date  # silencia lint


def test_sem_tax_code_padrao_usa_aliquota_da_nota():
    from decimal import Decimal

    from app.database import ParticipacaoPagamentoDB
    from app.services.nfse_pagamento import gerar_pagamento_para_nfse

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with sessionmaker(bind=eng)() as db:
        part_id = _seed_contrato_participacao(db)
        nid = _nfse(db, part_id, "13", 1000, 970, "2026-05-10")
        pag = db.get(ParticipacaoPagamentoDB, gerar_pagamento_para_nfse(db, nid).pagamento_id)
        assert pag.tax_code_id is None
        assert pag.imposto_total == Decimal("30.00") and pag.valor_liquido_recebido == Decimal("970.00")
        assert pag.valor_participacao == Decimal("97.00")


def test_manual_zera_recebimento_apos_fim_do_vinculo():
    """Vinculo ainda 'ativo' mas com data_fim: recebimento depois da data nao gera participacao."""
    from datetime import date
    from decimal import Decimal

    from app.database import ParticipacaoDB
    from app.services.pagamento_participacao import Recebimento, registrar

    db = _db_com_tax_code()
    part_id = _seed_contrato_participacao(db)
    db.execute(text("UPDATE participacoes SET data_fim_vinculo = '2026-03-31'"))
    db.commit()
    p = db.get(ParticipacaoDB, part_id)
    pag = registrar(db, p, Recebimento(data_recebimento=date(2026, 5, 10), valor_bruto=Decimal("1000")),
                    registrado_por="x@x.com")
    assert pag.valor_participacao == 0 and "término do vínculo" in pag.observacoes
