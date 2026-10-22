"""Edicao de contrato salvo: controle de versao, contrato enviado/assinado, um DOCX por versao,
cliente_docs e ficha de participacao acompanhando o PUT."""
import copy
import io
import json

import pytest
from docx import Document

from app.database import ContractDB, ContractVersionDB, ParticipacaoDB, SessionLocal
from tests.test_documentos_complementares import auth_e_origem  # noqa: F401  (fixture autouse: login + banco)

CPF_A, CPF_B = "111.444.777-35", "529.982.247-25"


def _form(valor: float = 100, cpf: str = CPF_A) -> dict:
    return {
        "contratantes": [{
            "tipo": "PF", "nome": "Fulano de Tal", "nacionalidade": "brasileiro", "cpf": cpf,
            "profissao": "empresario", "estado_civil": "Solteiro(a)", "endereco": "Rua X, 1", "email": "a@a.com",
        }],
        "escopos": [{"tipo": "consultoria_lgpd", "honorarios": ["pro_labore"],
                     "pro_labore": {"valor_total": valor, "tem_parcelamento": False}}],
        "acessorios": {"tem_reembolso": True, "reembolso_limitado": False, "tem_penalidade_inadimplemento": False},
        "participacao": {"tem_participacao": False},
    }


def _criar(client, **kw) -> str:
    r = client.post("/api/contract/generate", json=_form(**kw))
    assert r.status_code == 200, r.text
    return r.json()["contract_id"]


def _put(client, cid: str, form: dict, version=None):
    corpo = {"form_data": form}
    if version is not None:
        corpo["version"] = version
    return client.put(f"/api/contracts/{cid}", json=corpo)


def _texto(client, cid: str, version=None) -> str:
    r = client.get(f"/api/contract/{cid}/download", params={"version": version} if version else {})
    assert r.status_code == 200, r.text
    return "\n".join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)


def _contrato(cid: str) -> ContractDB:
    db = SessionLocal()
    try:
        c = db.query(ContractDB).filter_by(contract_id=cid).one()
        db.expunge(c)
        return c
    finally:
        db.close()


def _travar(cid: str, status: str):
    db = SessionLocal()
    try:
        db.query(ContractDB).filter_by(contract_id=cid).one().status = status
        db.commit()
    finally:
        db.close()


# ── item 2: controle de versao e contrato travado ───────────────────────────


def test_duas_abas_a_segunda_recebe_409_e_nada_e_gravado(client):
    cid = _criar(client, valor=100)
    assert _put(client, cid, _form(999), version=1).status_code == 200  # aba nova: v2
    r = _put(client, cid, _form(5), version=1)  # aba velha ainda na v1
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["codigo"] == "versao_desatualizada" and d["versao_atual"] == 2
    assert _contrato(cid).current_version == 2
    assert "999" in _texto(client, cid)


def test_put_com_a_versao_atual_segue_funcionando(client):
    cid = _criar(client)
    assert _put(client, cid, _form(200), version=1).json()["version"] == 2
    assert _put(client, cid, _form(300), version=2).json()["version"] == 3


@pytest.mark.parametrize("status", ["assinado", "enviado"])
def test_contrato_enviado_ou_assinado_nao_volta_a_rascunho(client, status):
    cid = _criar(client, valor=100)
    _travar(cid, status)
    r = _put(client, cid, _form(999), version=1)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["codigo"] == "contrato_travado" and d["motivo"] and d["sugestao"]
    c = _contrato(cid)
    assert c.status == status and c.current_version == 1
    assert "R$ 100,00" in _texto(client, cid)


def test_rollback_tambem_respeita_contrato_travado(client):
    cid = _criar(client)
    assert _put(client, cid, _form(999), version=1).status_code == 200
    _travar(cid, "assinado")
    r = client.post(f"/api/contracts/{cid}/rollback", params={"version": 1})
    assert r.status_code == 409 and _contrato(cid).status == "assinado"


# ── item 3: um DOCX por versao ──────────────────────────────────────────────


def test_download_de_cada_versao_traz_o_texto_da_propria_versao(client):
    cid = _criar(client, valor=100)
    _put(client, cid, _form(999), version=1)
    v1, v2 = _texto(client, cid, 1), _texto(client, cid, 2)
    assert "R$ 100,00" in v1 and "R$ 999,00" not in v1
    assert "R$ 999,00" in v2 and "R$ 100,00" not in v2
    assert "R$ 999,00" in _texto(client, cid)  # sem version = a mais nova


def test_versoes_tem_arquivos_distintos_e_rollback_cria_o_seu(client):
    cid = _criar(client, valor=100)
    _put(client, cid, _form(999), version=1)
    assert client.post(f"/api/contracts/{cid}/rollback", params={"version": 1}).status_code == 200
    db = SessionLocal()
    try:
        caminhos = [v.file_path for v in db.query(ContractVersionDB).filter_by(contract_id=cid).order_by(ContractVersionDB.version_number)]
    finally:
        db.close()
    assert len(caminhos) == 3 and len(set(caminhos)) == 3
    assert "R$ 100,00" in _texto(client, cid, 3) and "R$ 999,00" in _texto(client, cid, 2)


def test_versao_inexistente_nao_devolve_o_arquivo_mais_novo(client):
    cid = _criar(client)
    assert client.get(f"/api/contract/{cid}/download", params={"version": 9}).status_code == 404


def test_arquivo_da_v1_apagado_nao_e_substituido_pelo_da_mais_nova(client):
    """Em FS efemero o arquivo some: a v1 e' regenerada da form_data dela, nao copiada da v2."""
    import os

    cid = _criar(client, valor=100)
    _put(client, cid, _form(999), version=1)
    db = SessionLocal()
    try:
        for v in db.query(ContractVersionDB).filter_by(contract_id=cid):
            if os.path.exists(v.file_path):
                os.remove(v.file_path)
    finally:
        db.close()
    assert "R$ 100,00" in _texto(client, cid, 1)


# ── item 14: cliente_docs e ficha de participacao ───────────────────────────


def _ficha(cid: str):
    db = SessionLocal()
    try:
        return [(f.cliente_cpf_cnpj, f.aprovada) for f in db.query(ParticipacaoDB).filter_by(contract_id=cid)]
    finally:
        db.close()


def test_trocar_o_cpf_atualiza_busca_por_cpf_e_ficha(client):
    cid = _criar(client, cpf=CPF_A)
    assert json.loads(_contrato(cid).cliente_docs) == ["11144477735"]
    assert _ficha(cid) == [("111.444.777-35", False)]
    assert _put(client, cid, _form(cpf=CPF_B), version=1).status_code == 200
    assert json.loads(_contrato(cid).cliente_docs) == ["52998224725"]
    assert _ficha(cid) == [("529.982.247-25", False)]


def test_ficha_aprovada_pelo_financeiro_nao_e_tocada(client):
    cid = _criar(client, cpf=CPF_A)
    db = SessionLocal()
    try:
        db.query(ParticipacaoDB).filter_by(contract_id=cid).one().aprovada = True
        db.commit()
    finally:
        db.close()
    assert _put(client, cid, _form(cpf=CPF_B), version=1).status_code == 200
    assert _ficha(cid) == [("111.444.777-35", True)]
    assert json.loads(_contrato(cid).cliente_docs) == ["52998224725"]


# ── validacao de valores no PUT (regras do ContratoRequest, sem duplicar) ───


@pytest.mark.parametrize("tipo,campo,valor,trecho", [
    ("exito", "percentual", 150, "êxito"),
    ("exito", "percentual", -5, "êxito"),
    ("hora_trabalhada", "valor_hora", 0, "hora trabalhada"),
])
def test_put_recusa_valores_invalidos_com_422_e_nao_grava(client, tipo, campo, valor, trecho):
    from tests.test_varredura_honorarios import _req

    cid = _criar(client)
    corpo = _req(tipo, **{campo: valor})
    corpo["contratantes"] = _form()["contratantes"]
    r = _put(client, cid, corpo, version=1)
    assert r.status_code == 422, r.text
    det = r.json()["detail"]
    assert isinstance(det, list) and trecho in det[0]["msg"] and det[0]["loc"][:2] == ["body", "form_data"]
    assert _contrato(cid).current_version == 1


def test_put_com_valores_validos_continua_passando(client):
    from tests.test_varredura_honorarios import _req

    cid = _criar(client)
    corpo = _req("exito", percentual=100)
    corpo["contratantes"] = _form()["contratantes"]
    assert _put(client, cid, corpo, version=1).status_code == 200


def test_substabelecimento_assinado_nao_volta_a_rascunho_e_sugere_criar_novo(client):
    from tests.test_documentos_complementares import PROC_A, SUBSTABELECIMENTO

    sub = {**SUBSTABELECIMENTO, "processos": [PROC_A]}
    r = client.post("/api/documentos/substabelecimento", json=sub)
    assert r.status_code == 200, r.text
    cid = r.json()["contract_id"]
    _travar(cid, "assinado")
    resp = _put(client, cid, sub, version=1)
    assert resp.status_code == 409
    d = resp.json()["detail"]
    assert d["codigo"] == "contrato_travado" and "novo substabelecimento" in d["sugestao"]
    assert _contrato(cid).status == "assinado"
