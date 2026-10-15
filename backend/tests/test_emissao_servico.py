"""Servico de emissao de NFS-e: idempotencia, uma nota viva por fatura, nunca reenviar as cegas,
consulta pela DPS e eventos sem segredo. O SEFIN e simulado com httpx.MockTransport (sem rede)."""
from __future__ import annotations

import base64
import datetime
import gzip
import json
import os

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from lxml import etree
from sqlalchemy import text

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import ContractDB, SessionLocal
from app.main import app
from app.models.emissao_db import EmissorConfigDB, FaturaDB, NfseEmitidaDB
from app.services import emissao

CNPJ = "25463159000173"
SENHA = "senha-secreta-de-teste"
NS = "http://www.sped.fazenda.gov.br/nfse"
CHAVE = "NFS" + "3" * 47


def _pfx() -> bytes:
    chave = rsa.generate_private_key(65537, 2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"ESCRITORIO TESTE:{CNPJ}")])
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
            .serial_number(1).not_valid_before(datetime.datetime(2025, 1, 1))
            .not_valid_after(datetime.datetime(2035, 1, 1)).sign(chave, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(
        b"t", chave, cert, None, serialization.BestAvailableEncryption(SENHA.encode()))


def _como(role: str):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id=f"t-{role}", email=f"{role}@test.local", name=role.title(), role=role)


class Sefin:
    """SEFIN de mentira: grava o que recebeu e responde conforme o cenario."""

    def __init__(self):
        self.posts: list[bytes] = []
        self.gets: list[str] = []
        self.post_resp = lambda req: httpx.Response(201, json=self.sucesso())
        self.get_dps_resp = lambda req: httpx.Response(404, json={"erros": [{"Codigo": "E2404", "Descricao": "nao ha"}]})

    def sucesso(self):
        xml = (f'<NFSe xmlns="{NS}"><infNFSe Id="{CHAVE}"><nNFSe>752</nNFSe>'
               f'<valores><vISSQN>75.00</vISSQN></valores></infNFSe></NFSe>').encode()
        return {"chaveAcesso": CHAVE[3:], "nfseXmlGZipB64": base64.b64encode(gzip.compress(xml)).decode()}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        assert req.url.host == "sefin.producaorestrita.nfse.gov.br", req.url  # nunca outro host
        path = req.url.path
        if req.method == "POST" and path.endswith("/nfse"):
            self.posts.append(gzip.decompress(base64.b64decode(json.loads(req.content)["dpsXmlGZipB64"])))
            return self.post_resp(req)
        self.gets.append(path)
        if "/dps/" in path:
            return self.get_dps_resp(req)
        return httpx.Response(200, json=self.sucesso())

    def cliente(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


@pytest.fixture
def sefin(monkeypatch):
    s = Sefin()
    monkeypatch.setattr(emissao, "_cliente", lambda ctx: s.cliente())
    return s


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "nfse_kek", base64.b64encode(os.urandom(32)).decode())
    app.state.limiter.enabled = False  # os testes fazem dezenas de chamadas por minuto
    _como("financeiro")
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.state.limiter.enabled = True


@pytest.fixture
def client():
    return TestClient(app)


def _cenario(client, op_simp_nac="3", servico_extra=None, ativar=True):
    """Emissor ativo com certificado, servico, tomador, contrato que fatura pelo Honorario e 1 fatura aprovada."""
    dados = {"cnpj": CNPJ, "razao_social": "C&F", "inscricao_municipal": "03656630021", "op_simp_nac": op_simp_nac,
             "reg_ap_trib_sn": "1" if op_simp_nac == "3" else None, "serie_dps": "900"}
    assert client.put("/api/emissor", json=dados).status_code == 200
    assert client.post("/api/emissor/certificado", files={"pfx": ("a.pfx", _pfx())}, data={"senha": SENHA}).status_code == 200
    if ativar:
        assert client.put("/api/emissor", json={**dados, "ativo": True}).status_code == 200
    with SessionLocal() as db:
        db.add(ContractDB(contract_id="C1", status="ativo", client_name="Cliente", client_email="c@x.com",
                          current_version=1, cliente_docs="[]"))
        db.commit()
    s = client.post("/api/servicos", json={"nome": "Honorários", "c_trib_nac": "171401", "c_trib_mun": "001",
                                           "nbs": "113019000", **(servico_extra or {})}).json()
    t = client.post("/api/tomadores", json={"documento": "11222333000181", "nome": "Cliente Ltda", "cep": "30130001",
                                            "logradouro": "Av. Afonso Pena", "numero": "100", "bairro": "Centro",
                                            "municipio_ibge": "3106200", "uf": "MG"}).json()
    assert client.put("/api/contratos/C1/faturamento", json={"origem": "honorario", "tomador_id": t["id"],
                                                             "servico_id": s["id"]}).status_code == 200
    return s, t


def _fatura(client, s, t, competencia="2026-10-01", aprovar=True, valor="1500.00"):
    f = client.post("/api/faturas", json={"contract_id": "C1", "tomador_id": t["id"], "servico_id": s["id"],
                                          "competencia": competencia, "valor_bruto": valor}).json()
    if aprovar:
        client.post(f"/api/faturas/{f['id']}/aprovar")
    return f


def _emitir(client, fatura_id, chave="k1"):
    return client.post(f"/api/faturas/{fatura_id}/emitir", headers={"Idempotency-Key": chave})


def _db_nota(nota_id):
    with SessionLocal() as db:
        n = db.get(NfseEmitidaDB, nota_id)
        db.expunge(n)
        return n


def _status_fatura(fid):
    with SessionLocal() as db:
        return db.get(FaturaDB, fid).status


# --- caminho feliz --------------------------------------------------------------

def test_emite_e_a_nota_fica_autorizada_com_xml_e_fatura_emitida(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    r = _emitir(client, f["id"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["status"], j["chave_acesso"], j["numero_nfse"], j["iss"], j["tem_xml"]) == ("autorizada", CHAVE[3:], "752", "75.00", True)
    assert (j["dps_serie"], j["dps_numero"], j["ambiente"], j["valor_servicos"]) == ("900", 1, "homologacao", "1500.00")
    assert _status_fatura(f["id"]) == "emitida"

    # a DPS enviada e a gravada, e leva a configuracao (nao constantes): regime, IM, cTribMun, NBS
    enviada = etree.fromstring(sefin.posts[0])
    assert _db_nota(j["id"]).xml_dps == sefin.posts[0]
    ns = {"n": NS}
    assert enviada.findtext(".//n:regApTribSN", namespaces=ns) == "1"
    assert enviada.findtext(".//n:prest/n:IM", namespaces=ns) == "03656630021"
    assert (enviada.findtext(".//n:cTribMun", namespaces=ns), enviada.findtext(".//n:cNBS", namespaces=ns)) == ("001", "113019000")
    assert enviada.findtext(".//n:toma/n:CNPJ", namespaces=ns) == "11222333000181"
    assert enviada.findtext(".//n:vServ", namespaces=ns) == "1500.00"
    assert enviada.findtext(".//n:tpAmb", namespaces=ns) == "2"
    assert enviada.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature") is not None
    assert enviada.find(".//n:IBSCBS", namespaces=ns) is None  # IBS/CBS e opcional por servico

    d = client.get(f"/api/nfse-emitidas/{j['id']}").json()
    assert [e["tipo"] for e in d["eventos"]] == ["enviada", "resposta"]


def test_numeracao_sequencial_por_nota_e_ibscbs_so_quando_o_servico_pede(client, sefin):
    s, t = _cenario(client, servico_extra={"incluir_ibscbs": True, "c_ind_op": "100301", "cst_ibscbs": "000",
                                           "c_class_trib": "000001"})
    f1, f2 = _fatura(client, s, t), _fatura(client, s, t, competencia="2026-09-01")
    assert _emitir(client, f1["id"], "a").json()["dps_numero"] == 1
    assert _emitir(client, f2["id"], "b").json()["dps_numero"] == 2
    assert etree.fromstring(sefin.posts[0]).find(f".//{{{NS}}}IBSCBS") is not None


def test_tomador_pessoa_fisica_vai_como_cpf(client, sefin):
    s, _ = _cenario(client)
    pf = client.post("/api/tomadores", json={"documento": "52998224725", "nome": "Maria"}).json()
    f = _fatura(client, s, pf)
    assert _emitir(client, f["id"]).json()["status"] == "autorizada"
    assert etree.fromstring(sefin.posts[0]).findtext(f".//{{{NS}}}toma/{{{NS}}}CPF") == "52998224725"


# --- idempotencia e uma nota viva -------------------------------------------------

def test_mesma_chave_devolve_a_mesma_nota_sem_novo_envio(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    a = _emitir(client, f["id"], "mesma").json()
    b = _emitir(client, f["id"], "mesma").json()
    assert a["id"] == b["id"] and len(sefin.posts) == 1


def test_outra_chave_com_nota_autorizada_nao_cria_segunda_nota(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    a = _emitir(client, f["id"], "k1").json()
    b = _emitir(client, f["id"], "k2").json()
    assert a["id"] == b["id"] and len(sefin.posts) == 1
    assert len(client.get("/api/nfse-emitidas").json()) == 1


def test_chave_de_outra_fatura_e_recusada(client, sefin):
    s, t = _cenario(client)
    f1, f2 = _fatura(client, s, t), _fatura(client, s, t, competencia="2026-09-01")
    _emitir(client, f1["id"], "k1")
    assert _emitir(client, f2["id"], "k1").status_code == 409


def test_corrida_de_duas_emissoes_a_segunda_cai_no_indice_do_banco(client, sefin, monkeypatch):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    _emitir(client, f["id"], "k1")
    sefin.posts.clear()
    with SessionLocal() as db:  # a outra requisicao ja criou a nota, mas esta ainda nao a viu
        db.execute(text("UPDATE faturas SET status='aprovada'"))
        db.commit()
    monkeypatch.setattr(emissao, "_nota_viva", lambda db, fid: None)
    r = _emitir(client, f["id"], "k2")
    assert r.status_code == 409 and "em andamento" in r.json()["detail"]
    assert sefin.posts == []
    with SessionLocal() as db:  # o numero gasto na tentativa foi desfeito junto
        assert db.execute(text("SELECT ultimo_numero FROM dps_sequence")).scalar() == 1


# --- rejeicao e nova tentativa ----------------------------------------------------

def _rejeita(sefin, codigo="E0312", msg="codigo de tributacao nao administrado"):
    sefin.post_resp = lambda req: httpx.Response(400, json={"erros": [{"Codigo": codigo, "Descricao": msg}]})


def test_rejeicao_guarda_codigo_e_mensagem_e_a_fatura_volta_para_aprovada(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    _rejeita(sefin)
    j = _emitir(client, f["id"]).json()
    assert (j["status"], j["erro_codigo"], j["tem_xml"]) == ("rejeitada", "E0312", False)
    assert "nao administrado" in j["erro_mensagem"]
    assert _status_fatura(f["id"]) == "aprovada"
    # a mesma chave devolve a rejeicao guardada, sem falar com o SEFIN de novo
    assert _emitir(client, f["id"]).json()["status"] == "rejeitada" and len(sefin.posts) == 1


def test_apos_rejeicao_nova_tentativa_gera_nova_dps_e_nova_nota(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    _rejeita(sefin)
    a = _emitir(client, f["id"], "k1").json()
    sefin.post_resp = lambda req: httpx.Response(201, json=sefin.sucesso())
    b = _emitir(client, f["id"], "k2").json()
    assert (a["dps_numero"], b["dps_numero"], b["status"]) == (1, 2, "autorizada") and a["id"] != b["id"]
    assert _status_fatura(f["id"]) == "emitida"


# --- sem resposta: nunca reenvia as cegas ---------------------------------------

def _sem_resposta(sefin):
    def h(req):
        raise httpx.ReadTimeout("timeout", request=req)
    sefin.post_resp = h


def test_timeout_deixa_processando_e_a_repeticao_consulta_em_vez_de_reenviar(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    _sem_resposta(sefin)
    j = _emitir(client, f["id"], "k1").json()
    assert j["status"] == "processando" and _status_fatura(f["id"]) == "emitindo"
    ev = client.get(f"/api/nfse-emitidas/{j['id']}").json()["eventos"]
    assert [e["tipo"] for e in ev] == ["enviada", "erro"] and ev[1]["payload"] == {"tipo": "ReadTimeout"}

    # repete (outra chave): consulta pela DPS, a nota existe no SEFIN -> autoriza, sem 2o POST
    sefin.get_dps_resp = lambda req: httpx.Response(200, json={"chaveAcesso": CHAVE[3:]})
    k = _emitir(client, f["id"], "k2").json()
    assert k["id"] == j["id"] and k["status"] == "autorizada" and k["tem_xml"] is True
    assert len(sefin.posts) == 1 and any("/dps/" in g for g in sefin.gets)
    assert _status_fatura(f["id"]) == "emitida"


def test_5xx_sem_erro_estruturado_tambem_nao_conclui_nem_reenvia(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    sefin.post_resp = lambda req: httpx.Response(502, text="<h1>Bad Gateway</h1>")
    j = _emitir(client, f["id"], "k1").json()
    assert j["status"] == "processando"
    ev = client.get(f"/api/nfse-emitidas/{j['id']}").json()["eventos"]
    assert ev[-1]["payload"]["http"] == 502 and "Bad Gateway" in ev[-1]["payload"]["texto"]
    _emitir(client, f["id"], "k2")
    assert len(sefin.posts) == 1


def test_consulta_nao_achou_so_conclui_depois_de_cinco_minutos(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    _sem_resposta(sefin)
    j = _emitir(client, f["id"]).json()
    novo = client.post(f"/api/nfse-emitidas/{j['id']}/consultar").json()
    assert novo["status"] == "processando"  # 404 agora ainda pode ser so demora

    with SessionLocal() as db:
        n = db.get(NfseEmitidaDB, j["id"])
        n.criado_em = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
        db.commit()
    velho = client.post(f"/api/nfse-emitidas/{j['id']}/consultar").json()
    assert (velho["status"], velho["erro_codigo"]) == ("rejeitada", "SEM_NOTA")
    assert _status_fatura(f["id"]) == "aprovada" and len(sefin.posts) == 1
    # liberada: nova emissao gera nova DPS
    sefin.post_resp = lambda req: httpx.Response(201, json=sefin.sucesso())
    assert _emitir(client, f["id"], "k9").json()["dps_numero"] == 2


def test_consulta_de_nota_que_nao_esta_processando_nao_chama_o_sefin(client, sefin):
    s, t = _cenario(client)
    j = _emitir(client, _fatura(client, s, t)["id"]).json()
    sefin.gets.clear()
    assert client.post(f"/api/nfse-emitidas/{j['id']}/consultar").json()["status"] == "autorizada"
    assert sefin.gets == []


# --- travas ---------------------------------------------------------------------

def test_exige_idempotency_key(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    assert client.post(f"/api/faturas/{f['id']}/emitir").status_code == 400
    assert _emitir(client, f["id"], "x" * 81).status_code == 400
    assert sefin.posts == []


def test_so_fatura_aprovada_e_de_contrato_do_honorario(client, sefin):
    s, t = _cenario(client)
    rascunho = _fatura(client, s, t, aprovar=False)
    r = _emitir(client, rascunho["id"])
    assert r.status_code == 409 and "Aprove" in r.json()["detail"]
    client.put("/api/contratos/C1/faturamento", json={"origem": "legalone"})
    aprovada = _fatura(client, s, t, competencia="2026-09-01")
    r = _emitir(client, aprovada["id"], "k2")
    assert r.status_code == 409 and "Legal One" in r.json()["detail"]
    assert _emitir(client, 9999, "k3").status_code == 404
    assert sefin.posts == []


def test_emissor_inativo_sem_config_ou_em_producao_nao_emite(client, sefin):
    s, t = _cenario(client, ativar=False)
    f = _fatura(client, s, t)
    assert _emitir(client, f["id"]).status_code == 409  # nao ativo
    dados = {"cnpj": CNPJ, "razao_social": "C&F", "op_simp_nac": "3", "reg_ap_trib_sn": "1"}
    client.put("/api/emissor", json={**dados, "ativo": True})
    with SessionLocal() as db:  # mesmo que alguem force 'producao' no banco, a emissao recusa
        db.execute(text("UPDATE emissor_config SET ambiente='producao'"))
        db.commit()
    r = _emitir(client, f["id"], "k2")
    assert r.status_code == 409 and "producao" in r.json()["detail"]
    assert sefin.posts == []


def test_regra_do_anexo_i_barra_antes_de_gastar_numero_de_dps(client, sefin):
    # ME/EPP pelo SN sem retencao nao pode informar aliquota (E0625)
    s, t = _cenario(client, servico_extra={"aliquota_iss": "5.00"})
    f = _fatura(client, s, t)
    r = _emitir(client, f["id"])
    assert r.status_code == 400 and "E0625" in r.json()["detail"]
    assert sefin.posts == []
    with SessionLocal() as db:
        assert db.execute(text("SELECT count(*) FROM dps_sequence")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM nfse_emitidas")).scalar() == 0
    assert _status_fatura(f["id"]) == "aprovada"


def test_servico_com_iss_retido_vai_com_tpretissqn_2_e_aliquota(client, sefin):
    s, t = _cenario(client, servico_extra={"aliquota_iss": "5.00", "iss_retido_padrao": True})
    assert _emitir(client, _fatura(client, s, t)["id"]).json()["status"] == "autorizada"
    enviada = etree.fromstring(sefin.posts[0])
    assert (enviada.findtext(f".//{{{NS}}}tpRetISSQN"), enviada.findtext(f".//{{{NS}}}pAliq")) == ("2", "5.00")


def test_competencia_no_futuro_e_certificado_ilegivel_nao_gastam_numero(client, sefin):
    s, t = _cenario(client)
    futura = _fatura(client, s, t, competencia="2099-01-01")
    assert _emitir(client, futura["id"]).status_code == 400
    f = _fatura(client, s, t, competencia="2026-09-01")
    with SessionLocal() as db:
        cfg = db.get(EmissorConfigDB, 1)
        cfg.cert_pfx_enc = b"lixo"
        db.commit()
    r = _emitir(client, f["id"], "k2")
    assert r.status_code == 409 and "ilegivel" in r.json()["detail"]
    assert sefin.posts == []
    with SessionLocal() as db:
        assert db.execute(text("SELECT count(*) FROM dps_sequence")).scalar() == 0


# --- segredo --------------------------------------------------------------------

def test_nada_de_segredo_em_eventos_nem_nas_respostas(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    _rejeita(sefin, "E0001", "mensagem do servidor")
    textos = [_emitir(client, f["id"]).text]
    j = client.get("/api/nfse-emitidas").json()[0]
    textos += [client.get(f"/api/nfse-emitidas/{j['id']}").text, client.get("/api/nfse-emitidas").text]
    with SessionLocal() as db:
        textos += [str(r) for r in db.execute(text("SELECT payload FROM nfse_emitida_eventos")).all()]
    for t_ in textos:
        assert SENHA not in t_ and "PRIVATE KEY" not in t_ and "dpsXmlGZipB64" not in t_ and "<DPS" not in t_


# --- leitura e download ---------------------------------------------------------

def test_xml_para_download_so_de_nota_autorizada(client, sefin):
    s, t = _cenario(client)
    ok = _emitir(client, _fatura(client, s, t)["id"], "a").json()
    r = client.get(f"/api/nfse-emitidas/{ok['id']}/xml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert f"NFSe-{CHAVE[3:]}.xml" in r.headers["content-disposition"]
    assert b"<nNFSe>752</nNFSe>" in r.content

    _rejeita(sefin)
    ruim = _emitir(client, _fatura(client, s, t, competencia="2026-09-01")["id"], "b").json()
    assert client.get(f"/api/nfse-emitidas/{ruim['id']}/xml").status_code == 404
    assert client.get("/api/nfse-emitidas/999/xml").status_code == 404


def test_listagem_filtra_e_leitor_le_mas_nao_age(client, sefin):
    s, t = _cenario(client)
    ok = _emitir(client, _fatura(client, s, t)["id"], "a").json()
    _rejeita(sefin)
    _emitir(client, _fatura(client, s, t, competencia="2026-09-01")["id"], "b")
    assert len(client.get("/api/nfse-emitidas").json()) == 2
    assert [n["id"] for n in client.get("/api/nfse-emitidas?status=autorizada").json()] == [ok["id"]]
    assert len(client.get(f"/api/nfse-emitidas?fatura_id={ok['fatura_id']}").json()) == 1

    _como("leitor")
    assert client.get("/api/nfse-emitidas").status_code == 200
    assert client.get(f"/api/nfse-emitidas/{ok['id']}/xml").status_code == 200
    assert client.post(f"/api/nfse-emitidas/{ok['id']}/consultar").status_code == 403
    assert client.post(f"/api/faturas/{ok['fatura_id']}/emitir", headers={"Idempotency-Key": "z"}).status_code == 403
    _como("advogado")
    assert client.get("/api/nfse-emitidas").status_code == 403


# --- decisoes da revisao da #120 -------------------------------------------------

def test_flag_de_producao_e_rechecada_a_cada_emissao(client, sefin, monkeypatch):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    with SessionLocal() as db:  # 'producao' forcado no banco, flag desligada
        db.execute(text("UPDATE emissor_config SET ambiente='producao'"))
        db.commit()
    r = _emitir(client, f["id"], "k1")
    assert r.status_code == 409 and "NFSE_EMISSAO_PRODUCAO_PERMITIDA" in r.json()["detail"]
    monkeypatch.setattr(settings, "nfse_emissao_producao_permitida", True)
    r = _emitir(client, f["id"], "k2")  # flag ligada: ainda nao implementado nesta etapa
    assert r.status_code == 409 and "nao esta implementada" in r.json()["detail"]
    assert sefin.posts == []


def test_cnpj_do_certificado_e_conferido_de_forma_exata_na_hora_de_usar(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    with SessionLocal() as db:  # emissor passa a outro CNPJ sem trocar o certificado
        db.execute(text("UPDATE emissor_config SET cnpj='11222333000181'"))
        db.commit()
    r = _emitir(client, f["id"])
    assert r.status_code == 409 and "nao e do CNPJ" in r.json()["detail"]
    assert sefin.posts == []
