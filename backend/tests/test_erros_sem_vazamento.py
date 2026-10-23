"""500 nunca devolve SQL, parametros nem texto cru do Azure; texto grande demais vira 422 legivel."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_contract_generator_fidelidade import _escopo, _req_escopos
from tests.test_documentos_complementares import auth_e_origem  # noqa: F401  (fixture autouse: login + banco)

SEGREDO = "AADSTS7000215: Invalid client secret"
SQL = "(psycopg2.errors.StringDataRightTruncation) [SQL: INSERT INTO contracts (client_name) VALUES (%(n)s)] [parameters: {'n': 'Fulano'}]"


def _form(nome="Fulano de Tal") -> dict:
    req = _req_escopos([_escopo("pro_labore")])
    req["contratantes"][0]["nome"] = nome
    return req


def _sem_vazamento(texto: str) -> None:
    for proibido in ("psycopg2", "[SQL", "parameters", "INSERT", "AADSTS", "Invalid client secret", "Traceback"):
        assert proibido not in texto


def test_nome_acima_de_256_da_422_legivel_sem_sql(client):
    r = client.post("/api/contract/generate", json=_form("A" * 300))
    assert r.status_code == 422
    assert "nome" in r.text and "256" in r.text
    _sem_vazamento(r.text)


def test_nome_de_256_ainda_passa(client):
    assert client.post("/api/contract/generate", json=_form("A" * 256)).status_code == 200


def test_texto_gigante_em_campo_livre_da_422(client):
    form = _form()
    form["acessorios"]["clausulas_adicionais"] = "x" * 20_001
    r = client.post("/api/contract/generate", json=form)
    assert r.status_code == 422 and "20000" in r.text


def test_aditivo_com_texto_gigante_da_422(client):
    r = client.post("/api/documentos/aditivo", json={
        "contrato_origem_id": "x", "objeto": "o", "data_contrato_origem": "2025-01-01",
        "alteracoes": [{"tipo": "adicionar", "texto": "y" * 30_000}]})
    assert r.status_code == 422 and "20000" in r.text
    _sem_vazamento(r.text)


def test_erro_do_gerador_nao_vaza_o_detalhe(client, monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError(SQL)

    monkeypatch.setattr("app.routers.contract.ContractGenerator.generate", quebra)
    r = client.post("/api/contract/generate", json=_form())
    assert r.status_code == 500
    _sem_vazamento(r.text)


def test_erro_nao_tratado_vira_500_generico():
    @app.get("/api/_teste_erro_interno")
    def _boom():
        raise RuntimeError(SQL)

    r = TestClient(app, raise_server_exceptions=False).get("/api/_teste_erro_interno")
    assert r.status_code == 500 and r.json()["detail"]
    _sem_vazamento(r.text)


def _contrato_para_email(client) -> str:
    r = client.post("/api/contract/generate", json=_form())
    assert r.status_code == 200, r.text
    return r.json()["contract_id"]


@pytest.mark.parametrize("modo", ["excecao", "resposta_com_erro"])
def test_email_com_erro_do_azure_sai_sanitizado(client, monkeypatch, modo):
    class Servico:
        async def send_email_with_attachment(self, **k):
            if modo == "excecao":
                raise RuntimeError(f"Failed to acquire Azure token: {SEGREDO}")
            return {"success": False, "error": f"401 - {SEGREDO}"}

    monkeypatch.setattr("app.routers.email.get_email_service", lambda: Servico())
    cid = _contrato_para_email(client)
    r = client.post("/api/email/send", json={"contract_id": cid, "destinatario_email": "a@a.com", "destinatario_nome": "A"})
    _sem_vazamento(r.text)
    assert r.status_code == 500 or r.json()["success"] is False
