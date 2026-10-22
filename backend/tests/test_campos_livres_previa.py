"""Campo livre digitado tem de chegar à IA e ao destaque da prévia mesmo quando o
contrato o escreve diferente (inicial, ponto final, espaços), e nenhum campo/honorário
pode ser pulado na coleta."""
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
