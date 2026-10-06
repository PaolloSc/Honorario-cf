"""Percentual na ficha de participacao sai em pt-BR ('10%', '10,5%'), nunca '10.0%'."""
from app.utils.currency import formatar_percentual
from app.utils.participacao import linhas_participacao


def test_formatar_percentual():
    assert formatar_percentual(10) == "10%"
    assert formatar_percentual("10.0") == "10%"
    assert formatar_percentual("10.5") == "10,5%"
    assert formatar_percentual("10,5") == "10,5%"
    assert formatar_percentual("a combinar") == "a combinar%"


def test_ficha_nao_imprime_float_cru():
    linhas = dict(linhas_participacao({
        "valor_tipo": "percentual",
        "valor_percentual": "10.0",
        "participantes": [{"nome": "Ana", "natureza": "Captação", "percentual": "7.5"}],
    }))
    assert linhas["Percentual"] == "10%"
    assert "7,5%" in linhas["Para quem — Ana"]
