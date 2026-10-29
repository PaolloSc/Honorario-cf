"""Varredura (itens 7, 8, 9, 11, 12, 13): regras de negócio que a tela exigia e o backend não."""
import pytest
from pydantic import ValidationError

from app.models.contract import ContratoRequest
from tests.test_contract_generator_fidelidade import _base_req, _escopo, _has, _paras_for


def _req(tipo, **campos):
    e = _escopo(tipo)
    e[tipo].update(campos)
    return _base_req(honorario=tipo, extra_escopo=e)


# ── 7. êxito variável não herda o percentual fixo escondido ───────────────


def test_exito_variavel_nao_imprime_o_percentual_fixo_que_ficou():
    paras = _paras_for(_req("exito", subtipo="percentual_variavel", percentual=10, base_calculo="x",
                              faixas_percentual=[{"faixa": "até R$ 100.000,00", "percentual": "8"}]))
    assert not _has(paras, "corresponderão a 10% (dez por cento)")
    assert _has(paras, "Os honorários de êxito incidirão sobre")


# ── 8. mensalidade sem data não inventa "dia 5" ───────────────────────────


def test_mensalidade_sem_vencimento_informado_nao_escreve_vencimento():
    paras = _paras_for(_req("mensalidade", dia_vencimento="", dia_vencimento_data=None, valor=1000))
    assert not _has(paras, "com vencimento")


# ── 9. mínimo no backend ──────────────────────────────────────────────────


def _com(**mudancas):
    req = _base_req()
    for k, v in mudancas.items():
        req[k] = v
    return req


def test_contratantes_vazio_e_recusado():
    with pytest.raises(ValidationError, match="contratante"):
        ContratoRequest(**_com(contratantes=[]))


def test_escopos_vazio_e_recusado():
    with pytest.raises(ValidationError, match="escopo"):
        ContratoRequest(**_com(escopos=[]))


def test_cpf_e_email_invalidos_sao_recusados():
    req = _base_req()
    req["contratantes"][0]["cpf"] = "123"
    with pytest.raises(ValidationError, match="CPF"):
        ContratoRequest(**req)
    req = _base_req()
    req["contratantes"][0]["email"] = "nao-e-email"
    with pytest.raises(ValidationError, match="Contratante 1: e-mail"):
        ContratoRequest(**req)


@pytest.mark.parametrize("pct", ["abc", "150", "-3"])
def test_percentual_de_participacao_invalido_e_recusado(pct):
    with pytest.raises(ValidationError, match="participação"):
        ContratoRequest(**_com(participacao={"tem_participacao": True, "valor_tipo": "percentual", "valor_percentual": pct}))


def test_participacao_valida_passa():
    ContratoRequest(**_com(participacao={"tem_participacao": True, "valor_tipo": "percentual", "valor_percentual": "10,5"}))
    ContratoRequest(**_com(participacao={"tem_participacao": True, "participantes": [{"nome": "A", "percentual": "50"}]}))


def test_valor_negativo_de_participacao_e_recusado():
    with pytest.raises(ValidationError, match="negativo"):
        ContratoRequest(**_com(participacao={"tem_participacao": True, "valor_tipo": "valor", "valor_monetario": -10}))


# ── 11. pró-labore mensal ─────────────────────────────────────────────────


def test_pro_labore_mensal_sem_parcelas_e_recusado():
    with pytest.raises(ValidationError, match="número de parcelas"):
        ContratoRequest(**_req("pro_labore", tipo_parcelamento="mensal", valor_total=12000))


def test_pro_labore_parcelas_que_nao_batem_com_o_total():
    with pytest.raises(ValidationError, match="não bate"):
        ContratoRequest(**_req("pro_labore", tipo_parcelamento="mensal", valor_total=12000, numero_parcelas=3, valor_parcela=1000))


def test_pro_labore_parcelas_que_batem_passam_inclusive_arredondamento():
    ContratoRequest(**_req("pro_labore", tipo_parcelamento="mensal", valor_total=12000, numero_parcelas=3, valor_parcela=4000))
    ContratoRequest(**_req("pro_labore", tipo_parcelamento="mensal", valor_total=10000, numero_parcelas=3, valor_parcela=3333.33))


# ── 12. permuta sem objeto, êxito "Outro" sem texto ───────────────────────


def test_permuta_sem_objeto_e_recusada():
    with pytest.raises(ValidationError, match="objeto da permuta"):
        ContratoRequest(**_req("permuta", objeto_permuta="  "))


def test_exito_outro_sem_texto_e_recusado():
    with pytest.raises(ValidationError, match="forma de pagamento"):
        ContratoRequest(**_req("exito", percentual=10, forma_pagamento="a definir"))


# ── 13. etiquetas na ficha do financeiro ──────────────────────────────────


def test_ficha_traz_etiquetas():
    from app.utils.participacao import linhas_participacao

    linhas = dict(linhas_participacao({"etiquetas": ["VIP", "Contencioso"]}))
    assert linhas.get("Etiquetas") == "VIP, Contencioso"


# ── CNPJ: numérico e alfanumérico (Receita, jul/2026) ─────────────────────


def _pj(cnpj):
    req = _base_req()
    req["contratantes"] = [{"tipo": "PJ", "cnpj": cnpj, "razao_social": "X Ltda", "endereco": "rua", "email": "a@a.com"}]
    return req


@pytest.mark.parametrize("cnpj", ["11.222.333/0001-81", "11222333000181", "12.ABC.345/01DE-35", "12abc34501de35"])
def test_cnpj_numerico_e_alfanumerico_passam(cnpj):
    ContratoRequest(**_pj(cnpj))


@pytest.mark.parametrize("cnpj", ["123", "12.ABC.345/01DE-AB", "12.ABC.345/01DE", ""])
def test_cnpj_invalido_e_recusado(cnpj):
    with pytest.raises(ValidationError, match="CNPJ"):
        ContratoRequest(**_pj(cnpj))


def test_erro_de_contratante_diz_qual():
    req = _base_req()
    req["contratantes"].append({**req["contratantes"][0], "cpf": "1"})
    with pytest.raises(ValidationError, match="Contratante 2: CPF"):
        ContratoRequest(**req)


def test_resumo_do_escopo_nao_traz_percentual_fixo_no_exito_variavel():
    from app.models.contract import EscopoItem
    from app.services.contract_generator import ContractGenerator

    e = EscopoItem(**_req("exito", subtipo="percentual_variavel", percentual=10)["escopos"][0])
    assert "10%" not in ContractGenerator()._preco_resumo(e)
