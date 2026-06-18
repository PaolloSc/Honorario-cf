"""Participacao: campos estruturados + migracao de dados antigos."""
from app.models.contract import Participacao


def test_novos_campos_estruturados():
    p = Participacao(
        tem_participacao=True,
        valor_tipo="percentual",
        valor_percentual="10",
        para_quem=["Bruno Advogado", "Ana Admin"],
        contato_financeiro_nome="Carlos",
        contato_financeiro_email="carlos@cli.com",
        contato_financeiro_telefone="(31) 99999-0000",
    )
    assert p.valor_tipo == "percentual"
    assert p.valor_percentual == "10"
    assert p.para_quem == ["Bruno Advogado", "Ana Admin"]
    assert p.contato_financeiro_email == "carlos@cli.com"


def test_migra_valor_legado_para_outro():
    p = Participacao(tem_participacao=True, percentual_ou_valor="20% sobre exito")
    assert p.valor_tipo == "outro"
    assert p.valor_outro == "20% sobre exito"


def test_migra_para_quem_string_para_lista():
    p = Participacao(tem_participacao=True, para_quem="Bruno Advogado")
    assert p.para_quem == ["Bruno Advogado"]


def test_para_quem_vazio_vira_lista_vazia():
    p = Participacao(tem_participacao=True, para_quem="")
    assert p.para_quem == []


def test_valor_monetario_float():
    p = Participacao(tem_participacao=True, valor_tipo="valor", valor_monetario=5000.0)
    assert p.valor_monetario == 5000.0
