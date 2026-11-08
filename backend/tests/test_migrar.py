"""`python -m app.migrar` e a comparacao de esquema."""
import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app import migrar as m
from app.database import Base


def _banco_novo(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'novo.db'}")
    monkeypatch.setattr(m, "engine", eng)
    # o env.py do Alembic le DATABASE_URL
    monkeypatch.setenv("DATABASE_URL", str(eng.url))
    return eng


def test_ha_uma_unica_cabeca_de_migration():
    assert len(ScriptDirectory.from_config(m._config()).get_heads()) == 1


def test_banco_vazio_sobe_pelos_modelos_e_fica_carimbado_no_head(tmp_path, monkeypatch):
    eng = _banco_novo(tmp_path, monkeypatch)
    assert m.migrar() == "baseline"
    assert set(inspect(eng).get_table_names()) >= set(Base.metadata.tables) | {"alembic_version"}
    with eng.connect() as c:
        versao = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert versao == ScriptDirectory.from_config(m._config()).get_current_head()
    assert m.migrar() == "upgrade"  # segunda vez: nada pendente


def test_banco_com_tabelas_e_sem_carimbo_e_recusado(tmp_path, monkeypatch):
    eng = _banco_novo(tmp_path, monkeypatch)
    Base.metadata.create_all(bind=eng)
    with pytest.raises(m.BancoSemCarimbo):
        m.migrar()
    assert "alembic_version" not in inspect(eng).get_table_names()  # recusar nao escreve nada


def test_comparar_esquema_acha_coluna_faltando(tmp_path):
    from scripts.comparar_esquema import diferencas

    eng = create_engine(f"sqlite:///{tmp_path / 'c.db'}")
    Base.metadata.create_all(bind=eng)
    with eng.connect() as c:
        assert diferencas(c) == []
        c.execute(text("DROP TABLE testemunhas"))
        assert "add_table: testemunhas" in diferencas(c)


def test_migrar_conhece_todas_as_tabelas_sem_depender_do_app_inteiro():
    """Num interpretador novo (sem app.main), o metadata de migrar ja' inclui as tabelas de NFS-e."""
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "-c", "import app.migrar; from app.database import Base; print(sorted(Base.metadata.tables))"],
        capture_output=True, text=True,
    )
    assert "nfse_recebidas" in r.stdout and "nfse_emitidas" in r.stdout, r.stderr


def test_passo_do_deploy_so_roda_em_production_e_nao_derruba_banco_sem_carimbo(tmp_path, monkeypatch):
    from scripts.deploy_migrar import executar

    chamadas = []
    assert executar({"VERCEL_ENV": "preview"}, lambda: chamadas.append(1)) == 0
    assert executar({}, lambda: chamadas.append(1)) == 0
    assert chamadas == []  # fora de production nao migra

    assert executar({"VERCEL_ENV": "production"}, lambda: "upgrade") == 0
    assert chamadas == []

    def sem_carimbo():
        raise m.BancoSemCarimbo("falta carimbo")

    assert executar({"VERCEL_ENV": "production"}, sem_carimbo) == 0  # avisa e segue

    def quebrada():
        raise RuntimeError("migration falhou")

    with pytest.raises(RuntimeError):  # erro real derruba o build
        executar({"VERCEL_ENV": "production"}, quebrada)
