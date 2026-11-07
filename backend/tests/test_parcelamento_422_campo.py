"""Regras de parcelamento devolvem o 422 com o caminho do campo (loc), para a tela marcar o campo."""
import copy

import pytest
from pydantic import ValidationError

from app.models.contract import ContratoRequest
from tests.test_contrato_versoes import _form
from tests.test_documentos_complementares import auth_e_origem  # noqa: F401  (fixture autouse: login + banco)


def _com_pl(**pl) -> dict:
    form = copy.deepcopy(_form())
    form["escopos"][0]["pro_labore"] = {"valor_total": 1000, **pl}
    return form


def _erros(form: dict) -> list[dict]:
    with pytest.raises(ValidationError) as e:
        ContratoRequest.model_validate(form)
    return e.value.errors()


@pytest.mark.parametrize("pl, campo, trecho", [
    ({"tipo_parcelamento": "mensal", "valor_parcela": 100}, "numero_parcelas", "precisa do número de parcelas"),
    ({"tipo_parcelamento": "mensal", "numero_parcelas": 10}, "valor_parcela", "precisa do número de parcelas"),
    ({"tipo_parcelamento": "mensal", "numero_parcelas": 10, "valor_parcela": 50}, "valor_parcela", "não bate com o valor total"),
    ({"tipo_parcelamento": "mensal", "data_primeira_parcela": "31/02/2027", "numero_parcelas": 2}, "data_primeira_parcela", "data da primeira parcela"),
    ({"tipo_parcelamento": "mensal", "data_primeira_parcela": "2027-01-10"}, "numero_parcelas", "parcelado precisa"),
])
def test_pro_labore_aponta_o_campo(pl, campo, trecho):
    [err] = _erros(_com_pl(**pl))
    assert err["loc"] == ("escopos", 0, "pro_labore", campo)
    assert err["type"] == "regra_contrato"
    assert err["msg"].startswith("Escopo 1: ") and trecho in err["msg"]


def test_adicional_aponta_o_indice_do_adicional():
    form = _com_pl(adicionais=[
        {"valor_total": 500},
        {"valor_total": 600, "tipo_parcelamento": "mensal", "numero_parcelas": 3, "valor_parcela": 100},
    ])
    [err] = _erros(form)
    assert err["loc"] == ("escopos", 0, "pro_labore", "adicionais", 1, "valor_parcela")


def test_previa_continua_aceitando_formulario_pela_metade():
    form = _com_pl(tipo_parcelamento="mensal")
    ContratoRequest.model_validate(form, context={"previa": True})


def test_api_devolve_loc_do_campo(client):
    r = client.post("/api/contract/generate", json=_com_pl(tipo_parcelamento="mensal", valor_parcela=100))
    assert r.status_code == 422
    [err] = r.json()["detail"]
    assert err["loc"] == ["body", "escopos", 0, "pro_labore", "numero_parcelas"]
    assert "precisa do número de parcelas" in err["msg"]
