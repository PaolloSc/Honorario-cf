"""Config do emissor: prestador, parametros fiscais e certificado cifrado. Sem rede.

O certificado e gerado aqui (autoassinado); nenhum .pfx ou senha real entra no repositorio."""
from __future__ import annotations

import base64
import datetime
import os

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.emissao_db import EmissorConfigDB
from app.services.emissor_cert import decifrar_certificado

CNPJ = "25463159000173"  # digitos verificadores validos
SENHA = "senha-secreta-de-teste"


def _pfx(cnpj: str = CNPJ, senha: str = SENHA, validade: datetime.datetime | None = None) -> bytes:
    chave = rsa.generate_private_key(65537, 2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"ESCRITORIO TESTE:{cnpj}")])
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
            .serial_number(1).not_valid_before(datetime.datetime(2025, 1, 1))
            .not_valid_after(validade or datetime.datetime(2035, 1, 1)).sign(chave, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(
        b"t", chave, cert, None, serialization.BestAvailableEncryption(senha.encode()))


def _como(role: str):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id=f"t-{role}", email=f"{role}@test.local", name=role.title(), role=role)


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "nfse_kek", base64.b64encode(os.urandom(32)).decode())
    monkeypatch.setattr(settings, "nfse_emissao_producao_permitida", False)
    app.state.limiter.enabled = False  # os testes fazem dezenas de chamadas por minuto
    _como("financeiro")
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.state.limiter.enabled = True


@pytest.fixture
def client():
    return TestClient(app)


DADOS = {
    "cnpj": "25.463.159/0001-73", "razao_social": "C&F ADVOGADOS", "inscricao_municipal": "03656630021",
    "op_simp_nac": "3", "reg_ap_trib_sn": "1", "reg_esp_trib": "0", "serie_dps": "900",
}


def _subir(client, pfx=None, senha=SENHA):
    return client.post("/api/emissor/certificado", files={"pfx": ("a1.pfx", pfx or _pfx())}, data={"senha": senha})


# --- permissao ----------------------------------------------------------------

@pytest.mark.parametrize("role", ["advogado", "leitor"])
def test_so_financeiro_ou_admin(client, role):
    _como(role)
    assert client.get("/api/emissor").status_code == 403
    assert client.put("/api/emissor", json=DADOS).status_code == 403
    assert _subir(client).status_code == 403


def test_admin_tambem_acessa(client):
    _como("admin")
    assert client.get("/api/emissor").status_code == 200


# --- dados do emissor ---------------------------------------------------------

def test_sem_config_devolve_configurado_falso(client):
    r = client.get("/api/emissor")
    assert r.status_code == 200 and r.json()["configurado"] is False


def test_salvar_e_ler_com_parametros_fiscais_como_configuracao(client):
    r = client.put("/api/emissor", json=DADOS)
    assert r.status_code == 200, r.text
    j = client.get("/api/emissor").json()
    assert (j["cnpj"], j["inscricao_municipal"], j["op_simp_nac"], j["reg_ap_trib_sn"], j["serie_dps"]) == (
        CNPJ, "03656630021", "3", "1", "900")
    assert j["ambiente"] == "homologacao" and j["ativo"] is False and j["tem_certificado"] is False


@pytest.mark.parametrize("ruim", [
    {"cnpj": "11111111111111"}, {"cnpj": "123"}, {"op_simp_nac": "9"},
    {"op_simp_nac": "1", "reg_ap_trib_sn": "1"},  # regime do SN so para ME/EPP
])
def test_dados_invalidos_sao_recusados(client, ruim):
    assert client.put("/api/emissor", json={**DADOS, **ruim}).status_code in (400, 422)


def test_producao_so_com_a_flag_explicita(client, monkeypatch):
    assert client.put("/api/emissor", json={**DADOS, "ambiente": "producao"}).status_code == 400
    assert client.get("/api/emissor").json()["configurado"] is False  # nada foi gravado
    monkeypatch.setattr(settings, "nfse_emissao_producao_permitida", True)
    assert client.put("/api/emissor", json={**DADOS, "ambiente": "producao"}).status_code == 200


def test_nao_ativa_sem_certificado(client):
    assert client.put("/api/emissor", json={**DADOS, "ativo": True}).status_code == 400


# --- certificado --------------------------------------------------------------

def test_certificado_fica_cifrado_e_a_resposta_nao_tem_segredo(client):
    client.put("/api/emissor", json=DADOS)
    pfx = _pfx()
    r = _subir(client, pfx)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["tem_certificado"] is True and CNPJ in j["cert_titular"] and j["cert_validade"] == "2035-01-01"
    assert SENHA not in r.text and base64.b64encode(pfx)[:40].decode() not in r.text

    with SessionLocal() as db:
        cfg = db.get(EmissorConfigDB, 1)
        assert pfx not in cfg.cert_pfx_enc and SENHA.encode() not in cfg.cert_senha_enc
        assert base64.b64encode(pfx) not in cfg.cert_pfx_enc
        assert decifrar_certificado(cfg) == (pfx, SENHA)  # volta igual, so em memoria
        audit = db.execute(text("SELECT payload_after FROM nfse_audit_log WHERE acao='emissor.certificado'")).scalar()
    assert SENHA not in audit and CNPJ in audit


def test_senha_errada_recusa_sem_vazar(client):
    client.put("/api/emissor", json=DADOS)
    r = _subir(client, senha="errada-123")
    assert r.status_code == 400 and "errada-123" not in r.text and SENHA not in r.text


def test_certificado_de_outro_cnpj_e_vencido_sao_recusados(client):
    client.put("/api/emissor", json=DADOS)
    r = _subir(client, _pfx(cnpj="11222333000181"))
    assert r.status_code == 400 and "CNPJ" in r.json()["detail"]
    r = _subir(client, _pfx(validade=datetime.datetime(2025, 6, 1)))
    assert r.status_code == 400 and "vencido" in r.json()["detail"]
    assert client.get("/api/emissor").json()["tem_certificado"] is False


def test_certificado_exige_o_emissor_salvo_e_a_kek(client, monkeypatch):
    assert _subir(client).status_code == 409
    client.put("/api/emissor", json=DADOS)
    monkeypatch.setattr(settings, "nfse_kek", "")
    assert _subir(client).status_code == 503


def test_trocar_o_cnpj_com_certificado_exige_novo_certificado(client):
    client.put("/api/emissor", json=DADOS)
    _subir(client)
    assert client.put("/api/emissor", json={**DADOS, "cnpj": "11222333000181"}).status_code == 409


def test_ativar_depois_do_certificado_e_novo_certificado_desativa(client):
    client.put("/api/emissor", json=DADOS)
    _subir(client)
    assert client.put("/api/emissor", json={**DADOS, "ativo": True}).json()["ativo"] is True
    assert _subir(client).json()["ativo"] is False


# --- erro de validacao nao pode devolver o corpo (senha) ----------------------

def test_422_nao_ecoa_a_senha_nem_o_pfx(client):
    client.put("/api/emissor", json=DADOS)
    # sem o arquivo: o FastAPI monta o 422 com o que recebeu
    r = client.post("/api/emissor/certificado", data={"senha": SENHA})
    assert r.status_code == 422 and SENHA not in r.text
    # JSON em vez de multipart, com a senha no corpo
    r = client.post("/api/emissor/certificado", json={"senha": SENHA, "pfx": "AAAA"})
    assert r.status_code == 422 and SENHA not in r.text


def test_422_de_campo_invalido_nao_ecoa_o_valor_recebido(client):
    r = client.put("/api/emissor", json={**DADOS, "inscricao_municipal": "VALOR-ECOADO-" * 3})
    assert r.status_code == 422 and "VALOR-ECOADO" not in r.text
    assert r.json()["detail"][0]["loc"] == ["body", "inscricao_municipal"]


def test_cnpj_do_certificado_e_igualdade_exata_nao_substring(client):
    # certificado cujo CN tem o CNPJ do emissor DENTRO de um numero maior: nao pode passar
    client.put("/api/emissor", json=DADOS)
    r = _subir(client, _pfx(cnpj="9" + CNPJ + "9"))
    assert r.status_code == 400 and "CNPJ" in r.json()["detail"]
