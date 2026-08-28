"""Participacao: campos estruturados + migracao de dados antigos."""
from app.models.contract import Participacao


def test_novos_campos_estruturados():
    p = Participacao(
        tem_participacao=True,
        valor_tipo="percentual",
        valor_percentual="10",
        participantes=[
            {"nome": "Bruno Advogado", "natureza": "Captação", "percentual": "15"},
            {"nome": "Ana Admin", "natureza": "Performance"},
        ],
        contato_financeiro_nome="Carlos",
        contato_financeiro_email="carlos@cli.com",
        contato_financeiro_telefone="(31) 99999-0000",
    )
    assert p.valor_tipo == "percentual"
    assert p.valor_percentual == "10"
    assert [pp.nome for pp in p.participantes] == ["Bruno Advogado", "Ana Admin"]
    assert p.participantes[0].natureza == "Captação"
    assert p.participantes[0].percentual == "15"
    assert p.contato_financeiro_email == "carlos@cli.com"


def test_migra_valor_legado_para_outro():
    p = Participacao(tem_participacao=True, percentual_ou_valor="20% sobre exito")
    assert p.valor_tipo == "outro"
    assert p.valor_outro == "20% sobre exito"


def test_migra_para_quem_legado_para_participantes():
    p = Participacao(
        tem_participacao=True,
        para_quem=["Bruno Advogado", "Ana Admin"],
        natureza="Captação",
        valor_percentual="10",
    )
    assert [pp.nome for pp in p.participantes] == ["Bruno Advogado", "Ana Admin"]
    assert all(pp.natureza == "Captação" for pp in p.participantes)
    assert all(pp.percentual == "10" for pp in p.participantes)


def test_migra_para_quem_legado_string_unico():
    p = Participacao(tem_participacao=True, para_quem="Bruno Advogado")
    assert [pp.nome for pp in p.participantes] == ["Bruno Advogado"]


def test_para_quem_vazio_nao_gera_participantes():
    p = Participacao(tem_participacao=True, para_quem="")
    assert p.participantes == []


def test_valor_monetario_float():
    p = Participacao(tem_participacao=True, valor_tipo="valor", valor_monetario=5000.0)
    assert p.valor_monetario == 5000.0


def test_campos_legalone_aceitos():
    p = Participacao(
        tem_participacao=False,
        categoria_cliente="Corporativo",
        etiquetas=["Trabalhista", "Consultivo"],
        listas_transmissao=["Newsletter"],
    )
    assert p.categoria_cliente == "Corporativo"
    assert p.etiquetas == ["Trabalhista", "Consultivo"]
    assert p.listas_transmissao == ["Newsletter"]


def test_campos_legalone_ausentes_em_contrato_antigo():
    p = Participacao(tem_participacao=True)
    assert p.categoria_cliente == ""
    assert p.etiquetas == []
    assert p.listas_transmissao == []


def test_campos_legalone_none_viram_vazios():
    p = Participacao(
        tem_participacao=True,
        categoria_cliente=None,
        etiquetas=None,
        listas_transmissao=None,
    )
    assert p.categoria_cliente == ""
    assert p.etiquetas == []
    assert p.listas_transmissao == []


def test_listas_legalone_migram_string_para_lista():
    p = Participacao(
        tem_participacao=True, etiquetas="Trabalhista", listas_transmissao="Newsletter"
    )
    assert p.etiquetas == ["Trabalhista"]
    assert p.listas_transmissao == ["Newsletter"]


def test_listas_legalone_string_vazia_vira_lista_vazia():
    p = Participacao(tem_participacao=True, etiquetas="", listas_transmissao="  ")
    assert p.etiquetas == []
    assert p.listas_transmissao == []
