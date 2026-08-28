"""Formatação da ficha de participação — o que a equipe efetivamente lê."""
from app.utils.participacao import linhas_participacao, valor_participacao


def _dict(linhas):
    return dict(linhas)


def test_participantes_saem_um_por_linha():
    """Cada advogado tem natureza/percentual proprios, entao vira uma linha por nome."""
    linhas = _dict(linhas_participacao({
        "participantes": [
            {"nome": "Ana Souza", "natureza": "Captação", "percentual": "10"},
            {"nome": "Bruno Lima", "natureza": "Performance"},
        ]
    }))
    assert linhas["Para quem — Ana Souza"] == "Captação, 10%"
    assert linhas["Para quem — Bruno Lima"] == "Performance"


def test_para_quem_legado_sai_separado_por_virgula():
    """Contratos antigos (sem participantes) caem no formato legado: uma lista + natureza única."""
    linhas = _dict(linhas_participacao({"para_quem": ["Ana Souza", "Bruno Lima"], "natureza": "Captação"}))
    assert linhas["Para quem"] == "Ana Souza, Bruno Lima"
    assert linhas["Natureza"] == "Captação"


def test_criterio_usa_os_campos_novos_do_wizard():
    """O wizard grava valor_tipo + campo do tipo; a ficha lia só o campo legado."""
    assert valor_participacao({"valor_tipo": "percentual", "valor_percentual": "10"}) == (
        "Percentual",
        "10%",
    )
    assert valor_participacao({"valor_tipo": "valor", "valor_monetario": 1234.5}) == (
        "Valor",
        "R$ 1.234,50",
    )
    assert valor_participacao({"valor_tipo": "outro", "valor_outro": "metade do êxito"}) == (
        "Critério",
        "metade do êxito",
    )


def test_criterio_cai_no_formato_antigo_quando_preciso():
    assert valor_participacao({"percentual_ou_valor": "10% do êxito"}) == (
        "Percentual/Valor",
        "10% do êxito",
    )
    assert valor_participacao({}) is None


def test_campos_vazios_nao_viram_linha():
    assert linhas_participacao({"natureza": "", "para_quem": []}) == []


def test_ficha_completa_na_ordem_da_leitura():
    linhas = linhas_participacao({
        "base_tipo": "escopo", "base_label": "Contencioso",
        "valor_tipo": "percentual", "valor_percentual": "15",
        "participantes": [
            {"nome": "Ana", "natureza": "Performance"},
            {"nome": "Bruno", "natureza": "Captação"},
        ],
        "responsavel_captacao": "Carlos",
        "responsavel_gestao": "Diana",
        "contato_financeiro_nome": "Eva",
        "contato_financeiro_email": "eva@cliente.com",
    })
    assert [r for r, _ in linhas] == [
        "Base", "Percentual", "Para quem — Ana", "Para quem — Bruno",
        "Resp. Captação", "Resp. Gestão", "Contato — Nome", "Contato — E-mail",
    ]
