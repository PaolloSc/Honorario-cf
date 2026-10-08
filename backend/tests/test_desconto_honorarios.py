"""Desconto por tipo de honorário, parcelamento do pró-labore, campos livres do êxito,
vigência em Acessórios e a prévia de honorários do pop-up do wizard."""
import pytest

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.models.contract import ContratoRequest
from app.utils.currency import percentual_com_extenso
from tests.test_contract_generator_fidelidade import _base_req, _escopo, _has, _paras_for

DESCONTO_PCT = {
    "tem_desconto": True, "desconto_tipo": "percentual", "desconto_percentual": 10,
    "desconto_condicao": "pagamento até a data de vencimento.",
}


def _req_com(hon: str, **campos) -> dict:
    e = _escopo(hon)
    if hon == "exito":
        e["exito"] = {"percentual": 20, "base_calculo": "benefício econômico"}
    elif hon == "permuta":
        e["permuta"] = {"objeto_permuta": "contabilidade"}
    e[hon].update(campos)
    return _base_req(honorario=hon, extra_escopo=e)


@pytest.mark.parametrize("hon", ["hora_trabalhada", "pro_labore", "mensalidade", "exito", "permuta"])
def test_desconto_percentual_em_cada_tipo(hon):
    paras = _paras_for(_req_com(hon, **DESCONTO_PCT))
    assert _has(paras, "Será concedido desconto de 10% (dez por cento) sobre o valor deste honorário. "
                       "A concessão do desconto fica condicionada ao seguinte: "
                       "pagamento até a data de vencimento.")


def test_desconto_livre_sem_condicao():
    paras = _paras_for(_req_com("pro_labore", tem_desconto=True, desconto_tipo="livre",
                                desconto_livre="R$ 500,00 na primeira parcela"))
    frase = next(p for p in paras if "Será concedido desconto" in p)
    assert frase == ("Será concedido desconto sobre o valor deste honorário, nos seguintes "
                     "termos: R$ 500,00 na primeira parcela.")


def test_desconto_desligado_ou_vazio_nao_gera_frase():
    assert not _has(_paras_for(_req_com("mensalidade", tem_desconto=False, desconto_percentual=10)),
                    "desconto")
    # ligado mas sem especificação: nada de "desconto de 0%"
    assert not _has(_paras_for(_req_com("mensalidade", tem_desconto=True,
                                        desconto_condicao="à vista")), "Será concedido desconto")


def test_percentual_com_extenso_decimal():
    assert percentual_com_extenso(2.25) == "2,25% (dois vírgula vinte e cinco por cento)"
    assert percentual_com_extenso(1.05) == "1,05% (um vírgula zero cinco por cento)"


def test_pro_labore_parcelamento_customizado():
    paras = _paras_for(_req_com("pro_labore", tipo_parcelamento="customizado",
                                parcelamento_customizado="50% na assinatura e 50% em 30 dias"))
    assert _has(paras, "O valor total de R$ 10.000,00 (dez mil reais) será pago da seguinte "
                       "forma: 50% na assinatura e 50% em 30 dias.")
    assert not _has(paras, "parcela única")


def test_pro_labore_customizado_sem_valor_nao_escreve_zero():
    paras = _paras_for(_req_com("pro_labore", valor_total=0, tipo_parcelamento="customizado",
                                parcelamento_customizado="a combinar"))
    assert _has(paras, "O honorário pró-labore será pago da seguinte forma: a combinar.")
    # (a tabela de escopo ainda mostra o valor; a frase nova nao)
    assert not any("R$ 0,00" in p and "seguinte forma" in p for p in paras)


def test_pro_labore_mensal_e_legado_tem_parcelamento():
    campos = {"numero_parcelas": 3, "valor_parcela": 1000, "vencimento_parcelas": "10"}
    novo = _paras_for(_req_com("pro_labore", tipo_parcelamento="mensal", **campos))
    legado = _paras_for(_req_com("pro_labore", tem_parcelamento=True, **campos))
    esperado = "será pago em 3 parcelas de R$ 1.000,00"
    assert _has(novo, esperado) and _has(legado, esperado)


def test_exito_vencimento_e_forma_de_parcelamento_livres():
    paras = _paras_for(_req_com("exito", vencimento="10 dias após o recebimento do Benefício",
                                forma_parcelamento="em até 3 parcelas mensais"))
    assert _has(paras, "Vencimento: 10 dias após o recebimento do Benefício.")
    assert _has(paras, "O honorário de êxito será parcelado da seguinte forma: "
                       "em até 3 parcelas mensais.")


def test_vigencia_em_acessorios():
    req = _base_req()
    req["acessorios"].update(vigencia_inicio="2026-11-01", vigencia_fim="2027-10-31")
    assert _has(_paras_for(req), "As Partes pactuam prazo específico de vigência, "
                                 "de 01/11/2026 a 31/10/2027.")
    assert not _has(_paras_for(_base_req()), "vigência, de")


def test_contrato_antigo_continua_abrindo_e_gerando():
    """Chaves que saíram do wizard ainda são aceitas e o texto não muda: a vigência
    antiga (no pró-labore) só migra ao abrir no wizard, não ao regenerar o .docx."""
    e = _escopo("pro_labore")
    e["honorarios"] = ["pro_labore", "exito", "hora_trabalhada"]
    e["pro_labore"].update(data_inicio="2026-01-01", data_fim="2026-12-31", duracao_meses=12)
    e["exito"] = {"percentual": 10, "vencimento_data": "2026-05-10",
                  "data_inicio": "2026-01-01", "data_fim": "2026-06-30", "duracao_meses": 6}
    e["hora_trabalhada"] = {"valor_hora": 300, "horas_trabalhadas": 12.5}
    req = _base_req(extra_escopo=e)

    assert ContratoRequest(**req).acessorios.vigencia_inicio is None
    paras = _paras_for(req)
    assert _has(paras, "Vencimento: em 10/05/2026.")
    assert not _has(paras, "vigência, de")


def test_previa_honorarios_endpoint(client):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="user"
    )
    e = _req_com("pro_labore", **DESCONTO_PCT)["escopos"]
    try:
        r = client.post("/api/contract/preview-honorarios", json={"escopos": e})
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 200
    assert r.text.startswith("<h3>")
    assert "OUTRAS DISPOSIÇÕES SOBRE HONORÁRIOS" in r.text
    assert "10% (dez por cento)" in r.text
    assert "CLÁUSULAS GERAIS" not in r.text


def test_exito_vencimento_livre_com_data_entra_como_digitado():
    # Revisão da #109: "até 30/06/2027" saía "Vencimento: em 30/06/2027."
    paras = _paras_for(_req_com("exito", vencimento="até 30/06/2027"))
    assert _has(paras, "Vencimento: até 30/06/2027.")
    assert not _has(paras, "em 30/06/2027")
    # Só a data, digitada sozinha, continua ganhando o "em".
    assert _has(_paras_for(_req_com("exito", vencimento="30/06/2027")), "Vencimento: em 30/06/2027.")
