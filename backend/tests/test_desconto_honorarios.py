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
    assert _has(paras, "Será concedido desconto de 10% (dez por cento) sobre estes honorários, "
                       "condicionado ao seguinte: pagamento até a data de vencimento.")


def test_desconto_livre_sem_condicao():
    paras = _paras_for(_req_com("pro_labore", tem_desconto=True, desconto_tipo="livre",
                                desconto_livre="R$ 500,00 na primeira parcela"))
    frase = next(p for p in paras if "Será concedido desconto" in p)
    assert frase == ("Será concedido desconto sobre estes honorários nos seguintes "
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
    assert _has(paras, "Os honorários pró-labore, no valor total de R$ 10.000,00 (dez mil reais), "
                       "serão pagos da seguinte forma: 50% na assinatura e 50% em 30 dias.")
    assert not _has(paras, "parcela única")


def test_pro_labore_customizado_sem_valor_nao_escreve_zero():
    paras = _paras_for(_req_com("pro_labore", valor_total=0, tipo_parcelamento="customizado",
                                parcelamento_customizado="a combinar"))
    assert _has(paras, "Os honorários pró-labore serão pagos da seguinte forma: a combinar.")
    assert not _has(paras, "R$ 0,00")


def test_pro_labore_mensal_e_legado_tem_parcelamento():
    campos = {"numero_parcelas": 3, "valor_parcela": 1000, "vencimento_parcelas": "10"}
    novo = _paras_for(_req_com("pro_labore", tipo_parcelamento="mensal", **campos))
    legado = _paras_for(_req_com("pro_labore", tem_parcelamento=True, **campos))
    esperado = "serão pagos em 3 (três) parcelas de R$ 1.000,00"
    assert _has(novo, esperado) and _has(legado, esperado)


def test_exito_vencimento_e_forma_de_parcelamento_livres():
    paras = _paras_for(_req_com("exito", vencimento="10 dias após o recebimento do Benefício",
                                forma_parcelamento="em até 3 parcelas mensais"))
    assert _has(paras, "Os honorários de êxito vencerão 10 dias após o recebimento do Benefício "
                       "e serão parcelados da seguinte forma: em até 3 parcelas mensais.")


def test_vigencia_em_acessorios():
    req = _base_req()
    req["acessorios"].update(vigencia_inicio="2026-11-01", vigencia_fim="2027-10-31")
    assert _has(_paras_for(req), "Fica pactuado o prazo específico de vigência "
                                 "de 01/11/2026 a 31/10/2027.")
    assert not _has(_paras_for(_base_req()), "prazo específico de vigência")
    req["acessorios"].update(vigencia_fim=None, vigencia_meses=12)
    assert _has(_paras_for(req), "vigência de 12 (doze) meses, contados de 01/11/2026.")


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
    assert _has(paras, "Os honorários de êxito vencerão em 10/05/2026.")
    assert not _has(paras, "prazo específico de vigência")


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
    html = r.json()["html"]
    assert html.startswith("<h3>")
    assert "OUTRAS DISPOSIÇÕES SOBRE HONORÁRIOS" in html
    assert "10% (dez por cento)" in html
    assert "CLÁUSULAS GERAIS" not in html
    # percentual e condicao digitada vem destacados em amarelo
    assert "<mark" in html and "pagamento até a data de vencimento" in html


def test_marcar_digitados_mostra_ia_ao_lado_do_digitado():
    from app.routers.contract import _marcar_digitados

    out = _marcar_digitados(
        "<p>condicionada ao seguinte: pagamento ate o vencimeto.</p>",
        ["pagamento ate o vencimeto"],
        [{"trecho": "vencimeto", "sugestao": "vencimento"}],
    )
    assert "<del" in out and ">vencimeto</del>" in out and ">vencimento</ins>" in out
    assert out.count("<mark") == 1


def test_exito_vencimento_livre_com_data_entra_como_digitado():
    # Revisão da #109: "até 30/06/2027" saía "Vencimento: em 30/06/2027."
    paras = _paras_for(_req_com("exito", vencimento="até 30/06/2027"))
    assert _has(paras, "Os honorários de êxito vencerão até 30/06/2027.")
    assert not _has(paras, "em 30/06/2027")
    # Só a data, digitada sozinha, continua ganhando o "em".
    assert _has(_paras_for(_req_com("exito", vencimento="30/06/2027")), "vencerão em 30/06/2027.")


@pytest.mark.parametrize("pct", [150, -1])
def test_desconto_percentual_fora_de_0_a_100_recusado_pela_api(pct):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ContratoRequest(**_req_com("mensalidade", tem_desconto=True, desconto_percentual=pct))
    assert ContratoRequest(**_req_com("mensalidade", tem_desconto=True, desconto_percentual=100))


def test_previa_sem_ia_configurada_avisa_em_vez_de_dizer_que_esta_ok(client, monkeypatch):
    from app.services import contract_reviewer

    monkeypatch.setattr(contract_reviewer, "is_configured", lambda: False)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="user"
    )
    e = _req_com("pro_labore", **DESCONTO_PCT)["escopos"]
    try:
        r = client.post("/api/contract/preview-honorarios", json={"escopos": e, "revisar": True})
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert "não configurada" in r.json()["erro"]


def test_previa_com_ia_manda_frase_de_contexto_e_separa_avisos(client, monkeypatch):
    from app.services import contract_reviewer

    visto = {}

    def falso(texto, avisar_ambiguidade=False):
        visto["texto"], visto["avisar"] = texto, avisar_ambiguidade
        return [
            {"trecho": "a gente", "problema": "informal", "sugestao": "o escritório"},
            {"trecho": "perca a ação", "problema": "condição vaga", "sugestao": "", "tipo": "aviso"},
            {"trecho": "Será concedido desconto", "problema": "frase fixa", "sugestao": "x"},
        ]

    monkeypatch.setattr(contract_reviewer, "is_configured", lambda: True)
    monkeypatch.setattr(contract_reviewer, "review_text", falso)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="user"
    )
    e = _req_com("pro_labore", tem_desconto=True, desconto_tipo="percentual", desconto_percentual=100,
                 desconto_condicao="caso a gente perca a ação")["escopos"]
    try:
        r = client.post("/api/contract/preview-honorarios", json={"escopos": e, "revisar": True}).json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert visto["avisar"] is True
    assert "Frase no contrato: Será concedido desconto" in visto["texto"]
    # a correção da frase fixa é descartada; o aviso vai separado e sem riscar o texto
    assert [f["trecho"] for f in r["findings"]] == ["a gente"]
    assert [a["trecho"] for a in r["avisos"]] == ["perca a ação"]
    assert "<del" in r["html"] and "perca a ação" in r["html"]


@pytest.mark.parametrize("tipos", [
    ["pro_labore", "mensalidade"],
    ["pro_labore", "mensalidade", "exito"],
])
def test_previa_com_varios_honorarios_traz_cada_desconto_livre(client, monkeypatch, tipos):
    """Vários honorários no mesmo escopo, cada um com desconto livre próprio (e um
    percentual): todos vão à IA e aparecem destacados na prévia."""
    from app.services import contract_reviewer

    enviado = {}
    monkeypatch.setattr(contract_reviewer, "is_configured", lambda: True)
    monkeypatch.setattr(contract_reviewer, "review_text", lambda t, avisar_ambiguidade=False: enviado.setdefault("t", t) and [])
    e = _escopo(tipos[0])
    e["honorarios"] = tipos
    e["exito"] = {"percentual": 20, "base_calculo": "benefício econômico"}
    e["mensalidade"] = {**_escopo("mensalidade")["mensalidade"]}
    livres = {}
    for i, t in enumerate(tipos):
        if t == tipos[-1] and len(tipos) == 3:
            e[t].update(DESCONTO_PCT)
            continue
        livres[t] = f"Até R$ {500 + i},00 de abatimento sobre {t}"  # inicial maiúscula: o contrato a desce
        e[t].update(tem_desconto=True, desconto_tipo="livre", desconto_livre=livres[t])
    req = _base_req(honorario=tipos[0], extra_escopo=e)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="user"
    )
    try:
        r = client.post("/api/contract/preview-honorarios", json={"escopos": req["escopos"], "revisar": True}).json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    for texto in livres.values():
        assert f"{texto[0].lower()}{texto[1:]}</mark>" in r["html"], texto
        assert texto in enviado.get("t", ""), texto
    if len(tipos) == 3:
        assert "10% (dez por cento)" in r["html"] and "<mark" in r["html"].split("10% (dez por cento)")[0][-200:]
