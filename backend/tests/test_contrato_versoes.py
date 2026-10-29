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


# ── parecer da Angela: cancelar envio, regeneracao por versao, contrato antigo, ficha ──


class _DocuSealFalso:
    def __init__(self, ok=True):
        self.ok, self.arquivadas = ok, []

    async def archive_submission(self, sid):
        self.arquivadas.append(sid)
        if not self.ok:
            raise RuntimeError("DocuSeal fora do ar")
        return True


def _marcar_enviado(cid: str, sid="777"):
    db = SessionLocal()
    try:
        c = db.query(ContractDB).filter_by(contract_id=cid).one()
        c.status = "enviado"
        db.query(ContractVersionDB).filter_by(contract_id=cid, version_number=c.current_version).one().docuseal_submission_id = sid
        db.commit()
    finally:
        db.close()


def _sid(cid: str):
    db = SessionLocal()
    try:
        return [v.docuseal_submission_id for v in db.query(ContractVersionDB).filter_by(contract_id=cid)]
    finally:
        db.close()


def test_cancelar_envio_arquiva_limpa_o_id_volta_a_rascunho_e_libera_a_edicao(client, monkeypatch):
    cid = _criar(client)
    _marcar_enviado(cid)
    assert _put(client, cid, _form(999), version=1).status_code == 409
    falso = _DocuSealFalso()
    monkeypatch.setattr("app.routers.docuseal.get_docuseal_service", lambda: falso)
    r = client.post(f"/api/docuseal/{cid}/cancelar-envio")
    assert r.status_code == 200, r.text
    assert falso.arquivadas == ["777"] and _contrato(cid).status == "rascunho" and _sid(cid) == [None]
    db = SessionLocal()
    try:
        from app.database import AuditLogDB
        log = db.query(AuditLogDB).filter_by(contract_id=cid, action="cancelamento_envio").one()
        assert "777" in log.detail  # id antigo fica no historico
    finally:
        db.close()
    assert _put(client, cid, _form(999), version=1).status_code == 200


def test_cancelar_envio_com_falha_no_docuseal_nao_muda_nada(client, monkeypatch):
    cid = _criar(client)
    _marcar_enviado(cid)
    monkeypatch.setattr("app.routers.docuseal.get_docuseal_service", lambda: _DocuSealFalso(ok=False))
    r = client.post(f"/api/docuseal/{cid}/cancelar-envio")
    assert r.status_code == 502 and "DocuSeal" in r.json()["detail"]
    assert _contrato(cid).status == "enviado" and _sid(cid) == ["777"]


def test_cancelar_envio_so_vale_para_enviado_e_assinado_continua_travado(client, monkeypatch):
    cid = _criar(client)
    monkeypatch.setattr("app.routers.docuseal.get_docuseal_service", lambda: _DocuSealFalso())
    assert client.post(f"/api/docuseal/{cid}/cancelar-envio").status_code == 409  # rascunho
    _marcar_enviado(cid)
    _travar(cid, "assinado")
    assert client.post(f"/api/docuseal/{cid}/cancelar-envio").status_code == 409
    assert _put(client, cid, _form(999), version=1).status_code == 409


def test_travado_olha_so_o_estado_atual_submission_antiga_nao_trava(client):
    cid = _criar(client)
    _marcar_enviado(cid)
    _travar(cid, "rascunho")  # status corrigido; o id da submissao continua gravado
    assert _put(client, cid, _form(999), version=1).status_code == 200


def _apagar_docx(cid: str):
    import os

    db = SessionLocal()
    try:
        for v in db.query(ContractVersionDB).filter_by(contract_id=cid):
            if v.file_path and os.path.exists(v.file_path):
                os.remove(v.file_path)
    finally:
        db.close()
    from app.routers.contract import get_generator

    gen = get_generator().output_dir / f"contrato_{cid}.docx"
    gen.unlink(missing_ok=True)


def test_arquivos_apagados_baixar_v1_e_depois_a_ultima_traz_cada_texto(client):
    cid = _criar(client, valor=100)
    _put(client, cid, _form(555), version=1)
    _apagar_docx(cid)
    assert "R$ 100,00" in _texto(client, cid, 1)
    assert "R$ 555,00" in _texto(client, cid)  # a ultima, depois da v1 regenerada
    assert "R$ 100,00" in _texto(client, cid, 1)
    _apagar_docx(cid)
    assert "R$ 555,00" in _texto(client, cid)
    assert "R$ 100,00" in _texto(client, cid, 1)


def test_contrato_antigo_com_versoes_no_mesmo_arquivo_regenera_a_antiga(client):
    """Antes deste PR todas as versoes apontavam para contrato_<id>.docx (so com o texto da mais nova)."""
    from app.routers.contract import get_generator

    cid = _criar(client, valor=100)
    _put(client, cid, _form(999), version=1)
    generico = str(get_generator().output_dir / f"contrato_{cid}.docx")
    db = SessionLocal()
    try:
        for v in db.query(ContractVersionDB).filter_by(contract_id=cid):
            v.file_path = generico
        db.commit()
    finally:
        db.close()
    assert "R$ 100,00" in _texto(client, cid, 1) and "R$ 999,00" not in _texto(client, cid, 1)
    assert "R$ 999,00" in _texto(client, cid)


def test_ficha_rascunho_complementada_pelo_financeiro_so_muda_cliente(client):
    cid = _criar(client, cpf=CPF_A)
    db = SessionLocal()
    try:
        f = db.query(ParticipacaoDB).filter_by(contract_id=cid).one()
        f.percentual_captacao, f.observacoes, f.beneficiario_email = 5.0, "ajuste do financeiro", "fin@cf.com"
        db.commit()
    finally:
        db.close()
    assert _put(client, cid, _form(cpf=CPF_B), version=1).status_code == 200
    db = SessionLocal()
    try:
        f = db.query(ParticipacaoDB).filter_by(contract_id=cid).one()
        assert (f.percentual_captacao, f.observacoes, f.beneficiario_email) == (5.0, "ajuste do financeiro", "fin@cf.com")
        assert f.cliente_cpf_cnpj == "529.982.247-25"
    finally:
        db.close()


def test_status_manual_nao_destrava_assinado_nem_volta_enviado_a_rascunho(client):
    cid = _criar(client)
    _travar(cid, "assinado")
    assert client.patch(f"/api/contracts/{cid}/status", params={"status": "rascunho"}).status_code == 409
    _travar(cid, "enviado")
    assert client.patch(f"/api/contracts/{cid}/status", params={"status": "rascunho"}).status_code == 409
    assert client.patch(f"/api/contracts/{cid}/status", params={"status": "assinado"}).status_code == 200


# ── ajustes da segunda revisao ──────────────────────────────────────────────


def test_apos_409_de_versao_salvar_sobre_a_atual_com_a_versao_nova_funciona(client):
    cid = _criar(client)
    assert _put(client, cid, _form(999), version=1).status_code == 200
    r = _put(client, cid, _form(5), version=1)
    assert r.status_code == 409
    atual = r.json()["detail"]["versao_atual"]  # a tela adota esta versao e reenvia
    assert _put(client, cid, _form(5), version=atual).json()["version"] == atual + 1


def test_status_manual_enviado_para_cancelado_e_bloqueado_e_sem_submissao_nao_marca(client):
    cid = _criar(client)
    # nunca foi enviado pelo DocuSeal: "enviado" manual continua barrado
    assert client.patch(f"/api/contracts/{cid}/status", params={"status": "enviado"}).status_code == 409
    assert _contrato(cid).status == "rascunho"
    _marcar_enviado(cid)
    r = client.patch(f"/api/contracts/{cid}/status", params={"status": "cancelado"})
    assert r.status_code == 409 and "Cancelar envio" in r.json()["detail"]
    assert _contrato(cid).status == "enviado" and _sid(cid) == ["777"]
    assert client.patch(f"/api/contracts/{cid}/status", params={"status": "assinado"}).status_code == 200


def test_cancelar_envio_404_do_docuseal_conta_como_ja_arquivada(client, monkeypatch):
    import httpx

    from app.services.docuseal import DocuSealService

    class Resp:
        status_code = 404

    async def delete(self, *a, **k):
        return Resp()

    monkeypatch.setattr(httpx.AsyncClient, "delete", delete)
    servico = DocuSealService()
    monkeypatch.setattr("app.routers.docuseal.get_docuseal_service", lambda: servico)
    cid = _criar(client)
    _marcar_enviado(cid)
    r = client.post(f"/api/docuseal/{cid}/cancelar-envio")
    assert r.status_code == 200, r.text
    assert _contrato(cid).status == "rascunho" and _sid(cid) == [None]


def test_assinado_em_papel_rascunho_para_assinado_manual_fica_na_auditoria(client):
    from app.database import AuditLogDB

    cid = _criar(client)
    r = client.patch(f"/api/contracts/{cid}/status", params={"status": "assinado"})
    assert r.status_code == 200 and _contrato(cid).status == "assinado"
    db = SessionLocal()
    try:
        log = db.query(AuditLogDB).filter_by(contract_id=cid, action="mudanca_status").one()
        assert "assinado fora do sistema" in log.detail and log.user_email and log.created_at
    finally:
        db.close()
    assert _put(client, cid, _form(999), version=1).status_code == 409  # e fica travado


def test_cancelado_nao_vira_assinado_manualmente(client):
    cid = _criar(client)
    assert client.patch(f"/api/contracts/{cid}/status", params={"status": "cancelado"}).status_code == 200
    r = client.patch(f"/api/contracts/{cid}/status", params={"status": "assinado"})
    assert r.status_code == 409 and _contrato(cid).status == "cancelado"


def test_cancelar_envio_404_do_docuseal_fica_na_auditoria(client, monkeypatch):
    import httpx

    from app.database import AuditLogDB
    from app.services.docuseal import DocuSealService

    class Resp:
        status_code = 404

    async def delete(self, *a, **k):
        return Resp()

    monkeypatch.setattr(httpx.AsyncClient, "delete", delete)
    servico = DocuSealService()
    monkeypatch.setattr("app.routers.docuseal.get_docuseal_service", lambda: servico)
    cid = _criar(client)
    _marcar_enviado(cid, "888")
    assert client.post(f"/api/docuseal/{cid}/cancelar-envio").status_code == 200
    db = SessionLocal()
    try:
        log = db.query(AuditLogDB).filter_by(contract_id=cid, action="cancelamento_envio").one()
        assert "404" in log.detail and "888" in log.detail
    finally:
        db.close()
