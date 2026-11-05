"""Pró-labore (e adicionais) e torna da permuta com parcelas automáticas na cláusula."""
from tests.test_contract_generator_fidelidade import _paras_for, _req_escopos


def _texto(escopo: dict) -> str:
    escopo.setdefault("tipo", "consultoria_lgpd")
    return "\n".join(_paras_for(_req_escopos([escopo])))


def _pl(**kw) -> dict:
    return {"honorarios": ["pro_labore"], "pro_labore": {"valor_total": 14000, "tipo_parcelamento": "mensal", **kw}}


def test_parcelas_automaticas_com_primeira_em_data_fixa():
    t = _texto(_pl(numero_parcelas=5, data_primeira_parcela="2026-12-15"))
    assert "R$ 14.000,00 (" in t
    assert "mensais e sucessivas de R$ 2.800,00 (" in t
    assert "a primeira com vencimento em 15/12/2026 e as demais todo dia 15" in t


def test_ultima_parcela_absorve_centavos_e_dia_proprio():
    t = _texto(_pl(valor_total=10000, numero_parcelas=3, data_primeira_parcela="2026-12-10", dia_vencimento=20))
    assert "sendo 2 (duas) parcelas de R$ 3.333,33 (" in t
    assert "a última de R$ 3.333,34 (" in t
    assert "todo dia 20" in t


def test_adicional_condicional_com_descricao_da_fase():
    pl = _pl(numero_parcelas=5, data_primeira_parcela="2026-12-15")
    pl["pro_labore"]["adicionais"] = [
        {"descricao_fase": "2ª instância", "valor_total": 14000, "tipo_parcelamento": "mensal",
         "numero_parcelas": 5, "data_primeira_parcela": "2027-06-10"},
        {"descricao_fase": "execução", "valor_total": 3000},
    ]
    t = _texto(pl)
    assert "Caso haja 2ª instância, os honorários pró-labore adicionais" in t
    assert "a primeira com vencimento em 10/06/2027" in t
    assert "Caso haja execução, os honorários pró-labore adicionais, no valor de R$ 3.000,00 (" in t
    assert "serão pagos em parcela única" in t


def test_contrato_antigo_mantem_o_texto_digitado():
    """Sem data da 1ª parcela, vale o formato antigo (valor_parcela digitado)."""
    t = _texto(_pl(numero_parcelas=5, valor_parcela=2800, vencimento_parcelas="15"))
    assert "5 (cinco) parcelas de R$ 2.800,00 (" in t
    assert "mensais e sucessivas" not in t
    assert "adicionais" not in t


def test_torna_da_permuta_parcelada():
    t = _texto({"honorarios": ["permuta"], "permuta": {
        "objeto_permuta": "consultoria", "tem_torna": True, "valor_torna": 6000,
        "numero_parcelas_torna": 4, "data_primeira_parcela_torna": "2026-12-05",
    }})
    assert "a título de torna, o valor total de R$ 6.000,00 (" in t
    assert "em 4 (quatro) parcelas mensais e sucessivas de R$ 1.500,00 (" in t
    assert "a primeira com vencimento em 05/12/2026 e as demais todo dia 05" in t


# Adicional (outra fase ou instância) em todo honorário com valor, não só no pró-labore.
import pytest
from pydantic import ValidationError

from app.models.contract import ContratoRequest
from tests.test_contract_generator_fidelidade import _escopo

_AD = {"descricao_fase": "2ª instância", "valor_total": 6000, "tipo_parcelamento": "mensal",
       "numero_parcelas": 3, "data_primeira_parcela": "2027-03-05"}


@pytest.mark.parametrize("hon", ["hora_trabalhada", "mensalidade", "exito"])
def test_adicional_nos_outros_honorarios(hon):
    esc = _escopo(hon)
    esc[hon]["adicionais"] = [dict(_AD)]
    t = "\n".join(_paras_for(_req_escopos([esc])))
    assert ("Caso haja 2ª instância, os honorários adicionais, no valor total de R$ 6.000,00 (seis mil reais), "
            "serão pagos em 3 (três) parcelas mensais e sucessivas de R$ 2.000,00 (dois mil reais), "
            "a primeira com vencimento em 05/03/2027 e as demais todo dia 05.") in t


@pytest.mark.parametrize("hon", ["hora_trabalhada", "mensalidade", "exito"])
def test_adicional_sem_valor_e_recusado(hon):
    esc = _escopo(hon)
    esc[hon]["adicionais"] = [{"descricao_fase": "execução", "valor_total": 0}]
    with pytest.raises(ValidationError, match="adicional de"):
        ContratoRequest(**_req_escopos([esc]))
