"""Campo livre digitado tem de chegar à IA e ao destaque da prévia mesmo quando o
contrato o escreve diferente (inicial, ponto final, espaços), e nenhum campo/honorário
pode ser pulado na coleta."""
import re

import pytest

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services import contract_reviewer
from tests.test_contract_generator_fidelidade import _base_req, _escopo


def _previa(client, monkeypatch, escopo):
    enviado = {}
    monkeypatch.setattr(contract_reviewer, "is_configured", lambda: True)
    monkeypatch.setattr(
        contract_reviewer, "review_text",
        lambda t, avisar_ambiguidade=False: enviado.setdefault("t", t) and [],
    )
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="l@test.com", name="L", role="user")
    try:
        req = _base_req(honorario=escopo["honorarios"][0], extra_escopo=escopo)
        r = client.post("/api/contract/preview-honorarios", json={"escopos": req["escopos"], "revisar": True}).json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    return r["html"], enviado.get("t", "")


def test_permuta_descricao_minuscula_chega_na_ia_e_no_destaque(client, monkeypatch):
    # o gerador capitaliza e põe ponto final: "imóvel…" sai "Imóvel…."
    e = _escopo("permuta")
    e["permuta"].update(descricao="imóvel avaliado em dois milhões")
    html, ia = _previa(client, monkeypatch, e)
    assert "imóvel avaliado em dois milhões" in ia
    assert "Imóvel avaliado em dois milhões</mark>" in html


@pytest.mark.parametrize("campo,valor", [
    ("desconto_condicao", "Pagamento   em  dia"),       # espaços repetidos
    ("desconto_livre", "Abatimento de 5%."),            # ponto final digitado
    ("desconto_livre", 'Valor "especial" do cliente'),  # aspas
])
def test_variacoes_de_digitacao_chegam_na_ia_e_no_destaque(client, monkeypatch, campo, valor):
    e = _escopo("pro_labore")
    e["pro_labore"].update(tem_desconto=True, desconto_tipo="livre", desconto_livre="x livre", desconto_condicao="x cond")
    e["pro_labore"][campo] = valor
    html, ia = _previa(client, monkeypatch, e)
    assert valor.strip() in ia
    assert html.count("<mark") >= 1 and "background:rgba(250,204,21" in html


def test_mesmo_texto_em_dois_honorarios_destaca_os_dois(client, monkeypatch):
    e = _escopo("pro_labore")
    e["honorarios"] = ["pro_labore", "mensalidade"]
    e["mensalidade"] = _escopo("mensalidade")["mensalidade"]
    for t in ("pro_labore", "mensalidade"):
        e[t].update(tem_desconto=True, desconto_tipo="livre", desconto_livre="abatimento combinado com o financeiro")
    html, _ = _previa(client, monkeypatch, e)
    assert html.count(">abatimento combinado com o financeiro</mark>") == 2


def test_trecho_da_ia_com_inicial_maiuscula_casa_com_texto_em_minuscula():
    from app.routers.contract import _marcar_digitados

    out = _marcar_digitados(
        "<p>nos seguintes termos: até R$ 500 de abatimento.</p>",
        ["até R$ 500 de abatimento"],
        [{"trecho": "Até R$ 500", "sugestao": "Até R$ 500,00"}],
    )
    assert "<del" in out and "<ins" in out


@pytest.mark.parametrize("onde,campo,valor", [
    ("permuta", "objeto_permuta", "contabilidade e consultoria"),
    ("exito", "forma_pagamento", "em duas vezes após o trânsito em julgado"),
])
def test_campos_antes_nao_coletados_vao_para_a_ia(onde, campo, valor):
    data = {"escopos": [{"tipo": "x", "honorarios": [], "numero_autos": None,
                         "permuta": {}, "exito": {}}]}
    if onde == "escopo":
        data["escopos"][0][campo] = valor
    else:
        data["escopos"][0][onde][campo] = valor
    assert valor in [t for _, t, _ in contract_reviewer.campos_abertos(data)]


def test_faixas_vao_para_a_ia():
    data = {"escopos": [{"mensalidade": {"faixas_preco": [{"faixa": "de 1 a 10 processos", "valor": "2000"}]},
                         "exito": {"faixas_percentual": [{"faixa": "acima de dois milhões", "percentual": "10"}]}}]}
    textos = [t for _, t, _ in contract_reviewer.campos_abertos(data)]
    assert "de 1 a 10 processos" in textos and "acima de dois milhões" in textos


def test_fronteira_de_palavra_sim_nao_marca_assim():
    from app.routers.contract import _achar_no_html

    assert _achar_no_html("<p>Assim fica combinado.</p>", "sim") is None
    assert _achar_no_html("<p>Assim ou sim, tanto faz.</p>", "sim") == "sim"
    assert _achar_no_html("<p>Pagamento em dia conforme combinado</p>", "pagamento em dia") == "Pagamento em dia"


def test_texto_curto_ou_percentual_so_marca_se_unico():
    from app.routers.contract import _achar_no_html

    duas = "<p>Desconto de 10% na parcela 1.</p><p>Multa de 10% ao ano.</p>"
    assert _achar_no_html(duas, "10%") is None
    assert _achar_no_html("<p>Desconto de 10% na parcela 1.</p>", "10%") == "10%"
    # texto longo repetido continua valendo (a mesma frase em dois honorários)
    longo = "<p>abatimento combinado com o financeiro</p><p>abatimento combinado com o financeiro</p>"
    assert _achar_no_html(longo, "abatimento combinado com o financeiro")


def test_nao_casa_dentro_de_tag():
    from app.routers.contract import _achar_no_html

    assert _achar_no_html('<p style="background">texto</p>', "background") is None


def test_destaques_sobrepostos_marcam_so_o_mais_longo():
    from app.routers.contract import _marcar_digitados

    out = _marcar_digitados(
        "<p>nos termos: pagamento em dia sempre.</p>",
        ["pagamento em dia", "em dia sempre", "pagamento em dia sempre"],
        [],
    )
    assert out.count("<mark") == 1 and "<mark" in out and out.count("</mark>") == 1
    assert ">pagamento em dia sempre</mark>" in out


def test_destaque_so_dentro_do_trecho_do_campo():
    from app.routers.contract import _marcar_digitados

    html = "<p>Cláusula A: pagamento em dia sempre.</p><p>Cláusula B: pagamento em dia sempre.</p>"
    b = html.index("<p>Cláusula B")
    out = _marcar_digitados(html, [("pagamento em dia sempre", [(b, len(html))])], [])
    assert out.count("<mark") == 1
    assert out.index("<mark") > out.index("Cláusula B")


def test_trecho_vazio_nao_marca_nada():
    from app.routers.contract import _marcar_digitados

    assert "<mark" not in _marcar_digitados("<p>pagamento em dia</p>", [("pagamento em dia", [])], [])


def test_campo_so_e_marcado_no_bloco_gerado_por_ele(client, monkeypatch):
    # o texto do desconto tambem aparece, igual, numa frase fixa de outra clausula
    # (permuta): so' o paragrafo do desconto leva o destaque.
    fixa = "serão remunerados mediante permuta"
    e = _escopo("pro_labore")
    e["permuta"] = _escopo("permuta")["permuta"]
    e["honorarios"] = ["pro_labore", "permuta"]
    e["pro_labore"].update(tem_desconto=True, desconto_tipo="livre", desconto_livre=fixa)
    html, _ = _previa(client, monkeypatch, e)
    marcas = [m for m in re.finditer(r"<mark[^>]*>([^<]*)</mark>", html) if m.group(1) == fixa]
    assert len(marcas) == 1
    inicio = html.rfind("<p>", 0, marcas[0].start())
    assert "permuta com os" not in html[inicio:html.index("</p>", marcas[0].start())]


def test_marcar_usa_fronteira_de_palavra():
    from app.routers.contract import _marcar_digitados

    out = _marcar_digitados("<p>Assim ficou, e sim, combinado.</p>", ["sim"], [])
    assert out.count("<mark") == 1 and ">sim</mark>" in out and "As<mark" not in out
    # texto longo dentro de palavra maior tambem nao marca
    assert "<mark" not in _marcar_digitados("<p>xpagamento em diay</p>", ["pagamento em dia"], [])


def test_texto_curto_repetido_vai_a_ia_mas_sem_destaque(client, monkeypatch):
    e = _escopo("pro_labore")
    e["pro_labore"].update(tem_desconto=True, desconto_tipo="livre", desconto_livre="x livre longa", desconto_condicao="o desconto")
    html, ia = _previa(client, monkeypatch, e)
    assert "o desconto" in ia and "x livre longa" in ia
    # "o desconto" (curto) aparece 2x no mesmo paragrafo: sem <mark> nele
    assert ">o desconto</mark>" not in html.lower() and ">x livre longa</mark>" in html


def test_a_definir_nao_vai_a_ia():
    data = {"escopos": [{"exito": {"forma_pagamento": "a definir"}}]}
    assert contract_reviewer.campos_abertos(data) == []
    data["escopos"][0]["exito"]["forma_pagamento"] = "em duas vezes após o trânsito"
    assert len(contract_reviewer.campos_abertos(data)) == 1


def test_achar_sem_destaque_aceita_texto_curto_repetido():
    from app.routers.contract import _achar_no_html

    duas = "<p>Desconto de 10% na parcela 1.</p><p>Multa de 10% ao ano.</p>"
    assert _achar_no_html(duas, "10%") is None
    assert _achar_no_html(duas, "10%", destaque=False) == "10%"
