"""Cadastros da emissao (servicos, tomadores, quem fatura o contrato) e faturas. Sem rede."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.database import ContractDB, ContractVersionDB, SessionLocal
from app.main import app

SERVICO = {"nome": "Honorários", "c_trib_nac": "171401", "c_trib_mun": "001", "nbs": "1.1301.90.00"}
TOMADOR = {"documento": "11.222.333/0001-81", "nome": "Cliente Ltda", "emails": ["cobranca@cliente.com"]}


def _como(role: str):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id=f"t-{role}", email=f"{role}@test.local", name=role.title(), role=role)


@pytest.fixture(autouse=True)
def _login():
    app.state.limiter.enabled = False  # os testes fazem dezenas de chamadas por minuto
    _como("financeiro")
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.state.limiter.enabled = True


@pytest.fixture
def client():
    return TestClient(app)


def _contrato(contratantes=None, contract_id="C1"):
    contratantes = contratantes if contratantes is not None else [{
        "tipo": "pj", "cnpj": "11.222.333/0001-81", "razao_social": "Cliente Ltda",
        "endereco": "Av. Afonso Pena, 100, Centro, Belo Horizonte/MG, CEP 30130-001", "email": "contato@cliente.com"}]
    with SessionLocal() as db:
        db.add(ContractDB(contract_id=contract_id, status="ativo", client_name="Cliente Ltda",
                          client_email="contato@cliente.com", current_version=1, cliente_docs="[]"))
        db.add(ContractVersionDB(contract_id=contract_id, version_number=1,
                                 form_data_json=json.dumps({"contratantes": contratantes})))
        db.commit()


def _tudo(client):
    _contrato()
    s = client.post("/api/servicos", json=SERVICO).json()
    t = client.post("/api/tomadores", json=TOMADOR).json()
    return s, t


def _fatura(s, t, **kw):
    return {"contract_id": "C1", "tomador_id": t["id"], "servico_id": s["id"], "competencia": "2026-10-15",
            "valor_bruto": "1500.00", **kw}


# --- permissao ------------------------------------------------------------------

@pytest.mark.parametrize("role", ["advogado", "leitor"])
def test_so_financeiro_ou_admin(client, role):
    _como(role)
    for metodo, url in [("get", "/api/servicos"), ("post", "/api/servicos"), ("get", "/api/tomadores"),
                        ("get", "/api/faturas"), ("post", "/api/faturas"), ("get", "/api/contratos/C1/faturamento")]:
        assert getattr(client, metodo)(url).status_code == 403, url


# --- servicos -------------------------------------------------------------------

def test_servico_guarda_os_parametros_fiscais_como_dados(client):
    r = client.post("/api/servicos", json={**SERVICO, "aliquota_iss": "5.00", "iss_retido_padrao": True})
    assert r.status_code == 201, r.text
    j = r.json()
    assert (j["c_trib_nac"], j["c_trib_mun"], j["nbs"], j["incluir_ibscbs"]) == ("171401", "001", "113019000", False)
    assert j["descricao_padrao"].startswith("Referente a servi")
    assert client.get("/api/servicos").json()[0]["id"] == j["id"]


@pytest.mark.parametrize("ruim", [
    {"c_trib_nac": "17.14.01"}, {"c_trib_mun": "1"}, {"nbs": "1130"}, {"aliquota_iss": "150"}, {"nome": ""},
])
def test_servico_invalido_e_recusado(client, ruim):
    assert client.post("/api/servicos", json={**SERVICO, **ruim}).status_code == 422


def test_ibscbs_e_opcional_mas_completo_quando_ligado(client):
    assert client.post("/api/servicos", json={**SERVICO, "incluir_ibscbs": True}).status_code == 400
    ok = client.post("/api/servicos", json={**SERVICO, "incluir_ibscbs": True, "c_ind_op": "100301",
                                            "cst_ibscbs": "000", "c_class_trib": "000001"})
    assert ok.status_code == 201 and ok.json()["incluir_ibscbs"] is True


def test_servico_nome_duplicado_patch_e_desativar(client):
    s = client.post("/api/servicos", json=SERVICO).json()
    assert client.post("/api/servicos", json=SERVICO).status_code == 409
    r = client.patch(f"/api/servicos/{s['id']}", json={"nbs": "113012000", "ativo": False})
    assert r.status_code == 200 and r.json()["nbs"] == "113012000"
    assert client.get("/api/servicos").json() == []  # inativos fora da lista padrao
    assert len(client.get("/api/servicos?todos=true").json()) == 1
    assert client.patch(f"/api/servicos/{s['id']}", json={"c_trib_nac": None}).status_code == 400
    assert client.patch(f"/api/servicos/{s['id']}", json={"inexistente": 1}).status_code == 422
    assert client.patch("/api/servicos/999", json={"nbs": None}).status_code == 404


# --- tomadores ------------------------------------------------------------------

def test_tomador_normaliza_documento_e_cep_e_barra_duplicado(client):
    r = client.post("/api/tomadores", json={**TOMADOR, "cep": "30130-001", "uf": "mg"})
    assert r.status_code == 201, r.text
    j = r.json()
    assert (j["documento"], j["cep"], j["uf"], j["origem"]) == ("11222333000181", "30130001", "MG", "manual")
    assert client.post("/api/tomadores", json=TOMADOR).status_code == 409
    assert client.post("/api/tomadores", json={**TOMADOR, "documento": "123"}).status_code == 422
    assert client.post("/api/tomadores", json={**TOMADOR, "documento": "99999999000100", "cep": "123"}).status_code == 422


def test_tomador_busca_por_nome_ou_documento_e_patch(client):
    t = client.post("/api/tomadores", json=TOMADOR).json()
    client.post("/api/tomadores", json={"documento": "52998224725", "nome": "Maria Silva"})
    assert [x["nome"] for x in client.get("/api/tomadores?q=maria").json()] == ["Maria Silva"]
    assert [x["nome"] for x in client.get("/api/tomadores?q=112223").json()] == ["Cliente Ltda"]
    r = client.patch(f"/api/tomadores/{t['id']}", json={"optante_simples": True, "municipio_ibge": "3106200"})
    assert r.json()["optante_simples"] is True
    assert client.patch(f"/api/tomadores/{t['id']}", json={"nome": None}).status_code == 400


def test_tomador_a_partir_do_contrato(client):
    _contrato()
    r = client.post("/api/tomadores/de-contrato/C1")
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["documento"], j["nome"], j["origem"], j["cep"]) == ("11222333000181", "Cliente Ltda", "contrato", "30130001")
    assert j["emails"] == ["contato@cliente.com"]
    assert client.post("/api/tomadores/de-contrato/C1").json()["id"] == j["id"]  # nao duplica
    assert client.post("/api/tomadores/de-contrato/NAO-EXISTE").status_code == 404


def test_tomador_de_contrato_escolhe_o_contratante_pelo_documento(client):
    _contrato([
        {"tipo": "pf", "nome": "Ana Souza", "cpf": "529.982.247-25", "endereco": "Rua A", "email": "ana@x.com"},
        {"tipo": "pf", "nome": "Bruno Lima", "cpf": "111.444.777-35", "endereco": "Rua B", "email": "bruno@x.com"},
    ])
    assert client.post("/api/tomadores/de-contrato/C1").json()["nome"] == "Ana Souza"
    assert client.post("/api/tomadores/de-contrato/C1?documento=111.444.777-35").json()["nome"] == "Bruno Lima"
    assert client.post("/api/tomadores/de-contrato/C1?documento=00000000000").status_code == 404


# --- quem fatura o contrato -----------------------------------------------------

def test_contrato_fatura_no_legalone_por_padrao_e_so_muda_de_proposito(client):
    s, t = _tudo(client)
    assert client.get("/api/contratos/C1/faturamento").json()["origem"] == "legalone"
    assert client.get("/api/contratos/NAO-EXISTE/faturamento").status_code == 404
    assert client.put("/api/contratos/C1/faturamento", json={"origem": "honorario"}).status_code == 400
    r = client.put("/api/contratos/C1/faturamento", json={
        "origem": "honorario", "tomador_id": t["id"], "servico_id": s["id"], "gera_rascunho_mensal": True})
    assert r.status_code == 200 and client.get("/api/contratos/C1/faturamento").json()["origem"] == "honorario"
    assert client.put("/api/contratos/C1/faturamento", json={"origem": "sap"}).status_code == 422
    assert client.put("/api/contratos/C1/faturamento", json={"origem": "legalone", "tomador_id": 999}).status_code == 400


# --- faturas --------------------------------------------------------------------

def test_fatura_a_mao_nasce_em_rascunho_com_competencia_no_dia_1(client):
    s, t = _tudo(client)
    r = client.post("/api/faturas", json=_fatura(s, t))
    assert r.status_code == 201, r.text
    j = r.json()
    assert (j["status"], j["competencia"], j["origem"], j["valor_bruto"]) == ("rascunho", "2026-10-01", "manual", "1500.00")
    assert j["descricao"] == s["descricao_padrao"] and j["criada_por"] == "financeiro@test.local"


@pytest.mark.parametrize("ruim", [{"valor_bruto": "0"}, {"valor_bruto": "-5"}, {"valor_bruto": "10.555"},
                                  {"parcela_num": 3, "parcela_total": 2}])
def test_fatura_invalida_e_recusada(client, ruim):
    s, t = _tudo(client)
    assert client.post("/api/faturas", json=_fatura(s, t, **ruim)).status_code in (400, 422)


def test_fatura_referencias_inexistentes_e_mes_duplicado(client):
    s, t = _tudo(client)
    assert client.post("/api/faturas", json={**_fatura(s, t), "contract_id": "X"}).status_code == 404
    assert client.post("/api/faturas", json={**_fatura(s, t), "tomador_id": 99}).status_code == 400
    assert client.post("/api/faturas", json={**_fatura(s, t), "servico_id": 99}).status_code == 400
    assert client.post("/api/faturas", json=_fatura(s, t)).status_code == 201
    assert client.post("/api/faturas", json=_fatura(s, t, competencia="2026-10-28")).status_code == 409
    assert client.post("/api/faturas", json=_fatura(s, t, competencia="2026-11-01")).status_code == 201


def test_so_rascunho_edita_exclui_e_aprova_uma_vez(client):
    s, t = _tudo(client)
    f = client.post("/api/faturas", json=_fatura(s, t)).json()
    assert client.patch(f"/api/faturas/{f['id']}", json={"valor_bruto": "1800.00", "descricao": "Out/2026"}).json()["valor_bruto"] == "1800.00"
    assert client.patch(f"/api/faturas/{f['id']}", json={"valor_bruto": None}).status_code in (400, 422)
    a = client.post(f"/api/faturas/{f['id']}/aprovar")
    assert a.status_code == 200 and a.json()["status"] == "aprovada" and a.json()["aprovada_por"] == "financeiro@test.local"
    assert client.post(f"/api/faturas/{f['id']}/aprovar").status_code == 409
    assert client.patch(f"/api/faturas/{f['id']}", json={"descricao": "x"}).status_code == 409
    assert client.delete(f"/api/faturas/{f['id']}").status_code == 409
    g = client.post("/api/faturas", json=_fatura(s, t, competencia="2026-11-01")).json()
    assert client.delete(f"/api/faturas/{g['id']}").status_code == 204
    assert client.delete(f"/api/faturas/{g['id']}").status_code == 404


def test_lista_com_faixa_de_totais_por_status_e_filtros(client):
    s, t = _tudo(client)
    a = client.post("/api/faturas", json=_fatura(s, t, valor_bruto="1000.00")).json()
    client.post("/api/faturas", json=_fatura(s, t, competencia="2026-11-01", valor_bruto="500.50"))
    client.post(f"/api/faturas/{a['id']}/aprovar")
    j = client.get("/api/faturas").json()
    assert len(j["itens"]) == 2
    assert j["totais"]["aprovada"] == {"quantidade": 1, "valor": "1000.00"}
    assert j["totais"]["rascunho"] == {"quantidade": 1, "valor": "500.50"}
    assert j["totais"]["emitida"] == {"quantidade": 0, "valor": "0"}
    assert [i["id"] for i in client.get("/api/faturas?status=aprovada").json()["itens"]] == [a["id"]]
    assert len(client.get("/api/faturas?competencia=2026-11-20").json()["itens"]) == 1
    assert client.get("/api/faturas?status=qualquer").status_code == 400
