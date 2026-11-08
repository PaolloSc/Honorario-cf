"""Consultas ao cadastro de pessoas do escritorio."""
from app.database import ColaboradorDB, SessionLocal
from app.services import pessoas


def _semear(db):
    db.add_all([
        ColaboradorDB(nome="Socia", email="Socia@cf.test", papel="socio", ativo=True, ordem=1),
        ColaboradorDB(nome="Adv", email="adv@cf.test", papel="advogado", ativo=True, ordem=2),
        ColaboradorDB(nome="Estag", email="est@cf.test", papel="estagiario", ativo=True, ordem=3),
        ColaboradorDB(nome="Ex Socio", email="ex@cf.test", papel="socio", ativo=False, ordem=4),
    ])
    db.commit()


def test_consultas_de_pessoas():
    db = SessionLocal()
    try:
        _semear(db)
        assert [c.nome for c in pessoas.listar_colaboradores(db)] == ["Socia", "Adv", "Estag"]
        assert [c.nome for c in pessoas.listar_colaboradores(db, so_participaveis=True)] == ["Socia", "Adv"]
        assert len(pessoas.listar_colaboradores(db, incluir_inativos=True)) == 4
        assert pessoas.eh_socio_ativo(db, " socia@CF.test ")
        assert not pessoas.eh_socio_ativo(db, "adv@cf.test")
        assert not pessoas.eh_socio_ativo(db, "ex@cf.test")  # inativo
        assert not pessoas.eh_socio_ativo(db, "")
        assert [c.nome for c in pessoas.socios_ativos_com_email(db)] == ["Socia"]
    finally:
        db.close()
