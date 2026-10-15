"""Modelos da emissao de NFS-e: travas do banco, migracao 0014 e SQL idempotente do Neon.

SQLite roda sempre. O Postgres (migracao, SQL manual, numeracao e indice parcial) roda quando
TEST_POSTGRES_URL esta definido (CI sobe um postgres:16)."""
from __future__ import annotations

import importlib.util
import os
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models.emissao_db as m
from app.database import Base, ContractDB

NOVAS = ["emissor_config", "dps_sequence", "servicos", "tomadores", "contrato_faturamento",
         "faturas", "nfse_emitidas", "nfse_emitida_eventos"]
BACKEND = Path(__file__).parents[1]
CNPJ = "25463159000173"


def _migracao():
    spec = importlib.util.spec_from_file_location("mig0014", BACKEND / "alembic/versions/0014_emissao_nfse.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tabelas_existentes():
    return [t for n, t in Base.metadata.tables.items() if n not in NOVAS]


def _assinatura(eng, tabela):
    """Colunas (nome, anulavel), uniques e indices de uma tabela: o que a migracao tem de reproduzir."""
    i = inspect(eng)
    cols = sorted((c["name"], c["nullable"]) for c in i.get_columns(tabela))
    uqs = sorted(tuple(u["column_names"]) for u in i.get_unique_constraints(tabela))
    idx = sorted((x["name"], tuple(x["column_names"]), bool(x["unique"])) for x in i.get_indexes(tabela))
    fks = sorted((tuple(f["constrained_columns"]), f["referred_table"]) for f in i.get_foreign_keys(tabela))
    return cols, uqs, idx, fks


# --- SQLite: travas do banco ---------------------------------------------------

@pytest.fixture
def db():
    assert sqlite3.sqlite_version_info >= (3, 35), "RETURNING exige SQLite >= 3.35"
    eng = create_engine("sqlite://")

    @event.listens_for(eng, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(ContractDB(contract_id="C1", status="ativo", client_name="X", client_email="x@x.com",
                         current_version=1, cliente_docs="[]"))
        s.add(m.ServicoDB(nome="Honorarios", c_trib_nac="171401", criado_por="t"))
        s.add(m.TomadorDB(documento="11222333000181", nome="Cliente"))
        s.commit()
        yield s


def _fatura(**kw):
    base = dict(contract_id="C1", tomador_id=1, servico_id=1, competencia=date(2026, 10, 1),
                descricao="Mensalidade", valor_bruto=1500, criada_por="t")
    return m.FaturaDB(**{**base, **kw})


def _nota(fatura_id, numero, status="processando", **kw):
    base = dict(fatura_id=fatura_id, status=status, ambiente="homologacao", cnpj_prestador=CNPJ, dps_serie="900",
                dps_numero=numero, idempotency_key=f"k{numero}", valor_servicos=1500,
                tomador_snapshot={}, servico_snapshot={}, emitida_por="t")
    return m.NfseEmitidaDB(**{**base, **kw})


def test_numeracao_atomica_separada_por_serie_e_ambiente(db):
    nums = [m.proximo_dps(db, CNPJ, "900", "homologacao") for _ in range(3)]
    assert nums == [1, 2, 3]
    assert m.proximo_dps(db, CNPJ, "900", "producao") == 1
    assert m.proximo_dps(db, CNPJ, "1", "homologacao") == 1


def test_config_do_emissor_e_linha_unica_e_homologacao_por_padrao(db):
    db.add(m.EmissorConfigDB(id=1, cnpj=CNPJ, razao_social="C&F"))
    db.commit()
    cfg = db.get(m.EmissorConfigDB, 1)
    assert (cfg.ambiente, cfg.op_simp_nac, cfg.serie_dps, cfg.ativo) == ("homologacao", "1", "900", False)
    db.add(m.EmissorConfigDB(id=2, cnpj="11222333000181", razao_social="Outro"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    cfg.ambiente = "sandbox"
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_parametros_fiscais_do_servico_sao_dados_e_ibscbs_e_opcional(db):
    s = db.get(m.ServicoDB, 1)
    assert (s.c_trib_nac, s.c_trib_mun, s.nbs, s.aliquota_iss, s.incluir_ibscbs) == ("171401", None, None, None, False)


def test_so_uma_nota_viva_por_fatura(db):
    db.add(_fatura())
    db.commit()
    db.add(_nota(1, 1))
    db.commit()
    db.add(_nota(1, 2, status="autorizada"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_apos_rejeicao_uma_nova_tentativa_e_aceita(db):
    db.add(_fatura())
    db.commit()
    db.add(_nota(1, 1, status="rejeitada", erro_codigo="E0312"))
    db.commit()
    db.add(_nota(1, 2))
    db.commit()
    assert db.query(m.NfseEmitidaDB).count() == 2


def test_idempotencia_e_dps_repetida_sao_barradas(db):
    db.add(_fatura())
    db.add(_fatura(competencia=date(2026, 11, 1)))
    db.commit()
    db.add(_nota(1, 1, status="rejeitada"))
    db.commit()
    db.add(_nota(2, 2, idempotency_key="k1"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(_nota(2, 1))  # mesma DPS (cnpj, ambiente, serie, numero)
    with pytest.raises(IntegrityError):
        db.commit()


def test_fatura_do_mes_duplicada_e_valor_zero_sao_barrados(db):
    db.add(_fatura())
    db.commit()
    db.add(_fatura())
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(_fatura(competencia=date(2026, 12, 1), valor_bruto=0))
    with pytest.raises(IntegrityError):
        db.commit()


def test_contrato_fatura_no_legalone_por_padrao(db):
    db.add(m.ContratoFaturamentoDB(contract_id="C1"))
    db.commit()
    assert db.get(m.ContratoFaturamentoDB, "C1").origem == "legalone"


# --- migracao 0014 ------------------------------------------------------------

def _aplica(eng, funcao):
    with eng.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            funcao()


def test_migracao_reproduz_o_schema_dos_modelos_e_desfaz():
    mig = _migracao()
    assert mig.down_revision == "0013_nfse_adn"
    via_migracao, via_modelos = create_engine("sqlite://"), create_engine("sqlite://")
    Base.metadata.create_all(via_migracao, tables=_tabelas_existentes())
    Base.metadata.create_all(via_modelos)
    _aplica(via_migracao, mig.upgrade)
    for t in NOVAS:
        assert _assinatura(via_migracao, t) == _assinatura(via_modelos, t), t
    _aplica(via_migracao, mig.downgrade)
    assert not set(NOVAS) & set(inspect(via_migracao).get_table_names())


# --- Postgres de verdade -------------------------------------------------------

pg = pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"),
                        reason="defina TEST_POSTGRES_URL para rodar contra Postgres de verdade")


@pytest.fixture
def pg_eng():
    eng = create_engine(os.environ["TEST_POSTGRES_URL"])
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng, tables=_tabelas_existentes())
    yield eng
    Base.metadata.drop_all(eng)


@pg
def test_pg_migracao_e_sql_manual_geram_o_mesmo_schema_dos_modelos(pg_eng):
    sql = (BACKEND / "sql/0014_emissao_nfse.sql").read_text(encoding="utf-8")
    mig = _migracao()
    ref = create_engine(os.environ["TEST_POSTGRES_URL"])  # mesmo banco: compara por esquemas
    _aplica(pg_eng, mig.upgrade)
    via_migracao = {t: _assinatura(pg_eng, t) for t in NOVAS}
    _aplica(pg_eng, mig.downgrade)

    for _ in range(2):  # idempotente: a segunda rodada nao pode falhar nem mudar nada
        with pg_eng.begin() as c:
            c.exec_driver_sql(sql)
    via_sql = {t: _assinatura(pg_eng, t) for t in NOVAS}
    assert via_sql == via_migracao

    Base.metadata.drop_all(ref)
    Base.metadata.create_all(ref)
    assert {t: _assinatura(ref, t) for t in NOVAS} == via_sql


@pg
def test_pg_sql_manual_com_tabelas_ja_criadas_pelo_create_all_nao_quebra(pg_eng):
    Base.metadata.create_all(pg_eng)  # o init_db do app cria as tabelas na partida
    with pg_eng.begin() as c:
        c.exec_driver_sql((BACKEND / "sql/0014_emissao_nfse.sql").read_text(encoding="utf-8"))


@pg
def test_pg_numeracao_atomica_e_uma_nota_viva_por_fatura(pg_eng):
    Base.metadata.create_all(pg_eng)
    with Session(pg_eng) as s:
        s.add(ContractDB(contract_id="C1", status="ativo", client_name="X", client_email="x@x.com",
                         current_version=1, cliente_docs="[]"))
        s.add(m.ServicoDB(nome="Honorarios", c_trib_nac="171401", criado_por="t"))
        s.add(m.TomadorDB(documento="11222333000181", nome="Cliente"))
        s.commit()
        assert [m.proximo_dps(s, CNPJ, "900", "homologacao") for _ in range(3)] == [1, 2, 3]
        s.commit()
        s.add(_fatura())
        s.commit()
        s.add(_nota(1, 1))
        s.commit()
        s.add(_nota(1, 2, status="autorizada"))
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        s.add(_nota(1, 3, status="rejeitada"))
        s.commit()
        assert s.execute(text("SELECT count(*) FROM nfse_emitidas")).scalar() == 2
