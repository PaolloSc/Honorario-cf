"""Varredura do fluxo de honorários: penalidade desligada, limite do êxito e valores > 0."""
import re

import pytest
from pydantic import ValidationError

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.models.contract import ContratoRequest
from tests.test_contract_generator_fidelidade import _base_req, _escopo, _has, _paras_for, _preview_paras


def _req(tipo, **campos):
    e = _escopo(tipo)
    e[tipo].update(campos)
    req = _base_req(honorario=tipo, extra_escopo=e)
    return req


# ── 1. penalidade por inadimplemento ──────────────────────────────────────


def test_sem_penalidade_a_clausula_do_atraso_some_inteira():
    req = _base_req()
    assert req["acessorios"]["tem_penalidade_inadimplemento"] is False
    paras = _paras_for(req)
    assert not _has(paras, "multa de")
    assert not _has(paras, "O atraso no pagamento")
    assert _has(paras, "mudanças legislativas/regulatórias")  # vizinhas intactas


def test_com_penalidade_a_clausula_continua():
    req = _base_req()
    req["acessorios"]["tem_penalidade_inadimplemento"] = True
    assert _has(_paras_for(req), "multa de 10% (dez por cento)")


def test_sem_penalidade_numeracao_das_clausulas_gerais_sem_buraco():
    paras = _preview_paras(_base_req())
    nums = [m.group(1) for p in paras if (m := re.match(r"(\d+\.\d+)\. ", p))]
    sec = [n for n in nums if n.startswith(nums[-1].split(".")[0] + ".")]
    ordem = [int(n.split(".")[1]) for n in sec]
    assert ordem == list(range(1, len(ordem) + 1))


# ── 4. percentual de êxito ────────────────────────────────────────────────


@pytest.mark.parametrize("pct", [150, -5, 1000, 100.5])
def test_exito_fora_de_0_a_100_e_recusado(pct):
    with pytest.raises(ValidationError, match="percentual de êxito"):
        ContratoRequest(**_req("exito", percentual=pct))


@pytest.mark.parametrize("pct", [0, 10, 100, None])
def test_exito_dentro_do_limite_passa(pct):
    ContratoRequest(**_req("exito", percentual=pct))


# ── 10. valor zero ou negativo ────────────────────────────────────────────


@pytest.mark.parametrize("tipo,campo,rotulo", [
    ("hora_trabalhada", "valor_hora", "hora trabalhada"),
    ("pro_labore", "valor_total", "pró-labore"),
    ("mensalidade", "valor", "mensalidade"),
])
@pytest.mark.parametrize("valor", [0, -500])
def test_valor_zero_ou_negativo_e_recusado(tipo, campo, rotulo, valor):
    with pytest.raises(ValidationError, match=f"valor de {rotulo}"):
        ContratoRequest(**_req(tipo, **{campo: valor}))


def test_valor_positivo_passa():
    ContratoRequest(**_req("pro_labore", valor_total=1))


def test_honorario_desmarcado_nao_valida_dado_que_ficou_para_tras():
    req = _req("pro_labore", valor_total=10)
    req["escopos"][0]["hora_trabalhada"] = {"valor_hora": 0}
    ContratoRequest(**req)


def test_endpoint_generate_devolve_422(client):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="l@test.com", name="L", role="user")
    try:
        r = client.post("/api/contract/generate", json=_req("exito", percentual=150))
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 422


def test_previa_aceita_valor_zerado_formulario_pela_metade(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="l@test.com", name="L", role="user")
    try:
        req = _req("pro_labore", valor_total=0)
        r = client.post("/api/contract/preview-honorarios", json={"escopos": req["escopos"]})
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 200


# ── edicao de contrato salvo (PUT) valida como o contrato novo ────────────


def _salvar(client):
    r = client.post("/api/contract/generate", json=_req("hora_trabalhada", valor_hora=500))
    assert r.status_code == 200, r.text
    cid = r.json()["contract_id"]
    return cid, client.get(f"/api/contracts/{cid}/form-data").json()["form_data"]


def test_put_recusa_valor_zerado_e_o_modo_brando_continua_para_regerar(client):
    from app.services.contract_dispatch import parse_form_data
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="l@test.com", name="L", role="user")
    try:
        cid, form = _salvar(client)
        assert client.put(f"/api/contracts/{cid}", json={"form_data": form}).status_code == 200
        form["escopos"][0]["hora_trabalhada"]["valor_hora"] = 0
        r = client.put(f"/api/contracts/{cid}", json={"form_data": form})
        assert r.status_code == 422
        assert client.get(f"/api/contracts/{cid}").json()["current_version"] == 2  # nao gerou versao nova
        form["escopos"][0]["hora_trabalhada"]["valor_hora"] = 500
        form["contratantes"] = []
        assert client.put(f"/api/contracts/{cid}", json={"form_data": form}).status_code == 422
        form["contratantes"] = [{**_base_req()["contratantes"][0], "email": "xx"}]
        assert client.put(f"/api/contracts/{cid}", json={"form_data": form}).status_code == 422
        form["escopos"][0]["hora_trabalhada"]["valor_hora"] = 0
        parse_form_data(form)  # contrato antigo (download, e-mail, assinatura) segue regerando
        with pytest.raises(ValidationError):
            parse_form_data(form, estrito=True)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ── itens 5, 6 e 7 (modelo padrao decide onde entra) ──────────────────────


def _texto(req):
    return "\n".join(_paras_for(req))


def test_valor_diligencia_entra_nas_despesas_so_quando_preenchido():
    req = _base_req()
    assert "Cada diligência realizada" not in _texto(req)
    req["acessorios"]["valor_diligencia"] = 350
    texto = _texto(req)
    assert "Cada diligência realizada pelo C&F" in texto and "350,00" in texto


def test_periodo_da_hora_trabalhada_vira_prazo_determinado_em_8_1():
    req = _req("hora_trabalhada", valor_hora=500)
    assert "tempo indeterminado" in _texto(req)
    req["escopos"][0]["hora_trabalhada"].update(data_inicio="2026-01-01", data_fim="2026-12-31", duracao_meses=12)
    texto = _texto(req)
    assert "prazo determinado, de 01/01/2026 a 31/12/2026" in texto
    assert "tempo indeterminado" not in texto


def test_periodo_do_honorario_desmarcado_ou_vigencia_dos_acessorios_nao_mudam_o_8_1():
    req = _req("exito", percentual=10)
    req["escopos"][0]["hora_trabalhada"] = {"valor_hora": 1, "data_inicio": "2026-01-01", "data_fim": "2026-12-31"}
    assert "tempo indeterminado" in _texto(req)  # hora_trabalhada nao esta marcada
    req = _req("hora_trabalhada", valor_hora=500)
    req["escopos"][0]["hora_trabalhada"].update(data_inicio="2026-01-01", data_fim="2026-12-31")
    req["acessorios"].update(vigencia_inicio="2026-03-01", vigencia_fim="2026-09-30")
    texto = _texto(req)
    assert "tempo indeterminado" in texto and "01/01/2026 a 31/12/2026" not in texto
    assert "de 01/03/2026 a 30/09/2026" in texto


def test_exito_variavel_sem_faixa_completa_e_recusado_e_com_faixa_sai_a_tabela():
    req = _req("exito", subtipo="percentual_variavel", faixas_percentual=[{"faixa": "até 100 mil", "percentual": ""}])
    with pytest.raises(ValidationError):
        ContratoRequest(**req)
    req["escopos"][0]["exito"]["faixas_percentual"] = [{"faixa": "até R$ 100.000,00", "percentual": "10"}]
    assert "até R$ 100.000,00" in "\n".join(_paras_for(req))
