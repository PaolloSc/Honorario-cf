"""Substabelecimento: regerar ao mudar dados, acrescentar processo do mesmo outorgante,
nao mexer no que ja foi enviado/assinado, e nao deixar .docx orfao."""
import json

import pytest

from app.database import ContractDB, ContractVersionDB, SessionLocal
from app.services.contract_dispatch import get_generator
from tests.test_documentos_complementares import (  # noqa: F401  (auth_e_origem e' fixture autouse)
    DISTRATO,
    ORIGEM,
    PROC_A,
    PROC_B,
    SUBSTABELECIMENTO,
    _derivados_do_origem,
    _gerar,
    _id,
    _texto,
    auth_e_origem,
)

CNPJ = "11.222.333/0001-81"
PROC_C = {"tipo": "Processo", "numero": "7654321-70.2021.8.13.0702", "descricao": "Outorgante x Parte C"}


def _sub(**extra) -> dict:
    base = {**SUBSTABELECIMENTO, "outorgante": {"razao_social": "OUTORGANTE EXEMPLO LTDA", "cnpj": CNPJ}, "processos": [PROC_A]}
    return {**base, **extra}


def _form(contract_id: str) -> dict:
    db = SessionLocal()
    try:
        c = db.query(ContractDB).filter_by(contract_id=contract_id).one()
        v = db.query(ContractVersionDB).filter_by(contract_id=contract_id, version_number=c.current_version).one()
        return json.loads(v.form_data_json)
    finally:
        db.close()


def _versao(contract_id: str) -> int:
    db = SessionLocal()
    try:
        return db.query(ContractDB).filter_by(contract_id=contract_id).one().current_version
    finally:
        db.close()


def _travar(contract_id: str, status: str):
    db = SessionLocal()
    try:
        db.query(ContractDB).filter_by(contract_id=contract_id).one().status = status
        db.commit()
    finally:
        db.close()


def _editar(client, contract_id: str, **mudancas):
    form = {**_form(contract_id), **mudancas}
    r = client.put(f"/api/contracts/{contract_id}", json={"form_data": form})
    assert r.status_code == 200, r.text
    return r.json()


def _todos_substabelecimentos() -> int:
    db = SessionLocal()
    try:
        return db.query(ContractDB).filter_by(tipo_contrato="substabelecimento").count()
    finally:
        db.close()


# ── 1. mudar nome/processo regera o mesmo documento ─────────────────────────


def test_trocar_o_nome_do_outorgante_regera_sem_criar_outro(client):
    cid = _id(client, "substabelecimento", _sub())
    antes = _todos_substabelecimentos()
    _editar(client, cid, outorgante={"razao_social": "NOVO NOME LTDA", "cnpj": CNPJ})
    assert _versao(cid) == 2 and _todos_substabelecimentos() == antes
    assert "NOVO NOME LTDA" in _texto(client, cid)


def test_trocar_um_processo_regera_sem_criar_outro(client):
    cid = _id(client, "substabelecimento", _sub())
    _editar(client, cid, processos=[PROC_B])
    assert _versao(cid) == 2
    texto = _texto(client, cid)
    assert PROC_B["numero"] in texto and PROC_A["numero"] not in texto


def test_editar_o_distrato_regera_o_substabelecimento_que_nasceu_dele(client):
    r = _gerar(client, "distrato", DISTRATO)
    assert r.status_code == 200, r.text
    distrato, sub = r.json()["contract_id"], r.json()["documentos_gerados_junto"][0]
    assert _form(sub)["distrato_origem_id"] == distrato
    novo = {**_form(distrato)["substabelecimento"], "processos": [PROC_B]}
    resp = _editar(client, distrato, substabelecimento=novo)
    assert resp["documentos_regerados"] == [sub] and resp["documentos_gerados_junto"] == []
    assert _versao(sub) == 2 and len(_derivados_do_origem("substabelecimento")) == 1
    assert PROC_B["numero"] in _texto(client, sub)


def test_editar_o_distrato_sem_mudar_o_substabelecimento_nao_cria_versao(client):
    r = _gerar(client, "distrato", DISTRATO)
    distrato, sub = r.json()["contract_id"], r.json()["documentos_gerados_junto"][0]
    resp = _editar(client, distrato, objeto_contrato_origem="outro objeto")
    assert resp["documentos_regerados"] == [] and _versao(sub) == 1


@pytest.mark.parametrize("status", ["assinado", "enviado"])
def test_editar_o_distrato_com_substabelecimento_travado_cria_um_novo(client, status):
    r = _gerar(client, "distrato", DISTRATO)
    distrato, sub = r.json()["contract_id"], r.json()["documentos_gerados_junto"][0]
    _travar(sub, status)
    novo = {**_form(distrato)["substabelecimento"], "processos": [PROC_B]}
    resp = _editar(client, distrato, substabelecimento=novo)
    assert resp["documentos_regerados"] == [] and len(resp["documentos_gerados_junto"]) == 1
    assert _versao(sub) == 1 and PROC_B["numero"] not in _texto(client, sub)
    assert PROC_B["numero"] in _texto(client, resp["documentos_gerados_junto"][0])


# ── 2. mesmo outorgante: acrescenta o processo ──────────────────────────────


def test_existente_informa_o_substabelecimento_do_cliente(client):
    assert client.get("/api/documentos/substabelecimento-existente", params={"documento": CNPJ}).json() == {"existe": False}
    cid = _id(client, "substabelecimento", _sub())
    r = client.get("/api/documentos/substabelecimento-existente", params={"documento": "11222333000181"}).json()
    assert r["existe"] and r["contract_id"] == cid and r["pode_acrescentar"] and r["processos"] == [PROC_A["numero"]]


def test_mesmo_cnpj_acrescenta_o_processo_sem_duplicar(client):
    cid = _id(client, "substabelecimento", _sub())
    r = client.post(f"/api/documentos/substabelecimento?acrescentar_a={cid}", json=_sub(processos=[PROC_A, PROC_B]))
    assert r.status_code == 200, r.text
    assert r.json()["contract_id"] == cid and r.json()["processos_novos"] == 1
    assert _todos_substabelecimentos() == 1 and _versao(cid) == 2
    assert [p["numero"] for p in _form(cid)["processos"]] == [PROC_A["numero"], PROC_B["numero"]]
    texto = _texto(client, cid)
    assert texto.count(PROC_A["numero"]) == 1 and PROC_B["numero"] in texto


def test_acrescentar_so_processos_repetidos_nao_gera_versao(client):
    cid = _id(client, "substabelecimento", _sub())
    r = client.post(f"/api/documentos/substabelecimento?acrescentar_a={cid}", json=_sub())
    assert r.status_code == 200 and r.json()["processos_novos"] == 0
    assert _versao(cid) == 1 and _todos_substabelecimentos() == 1


def test_acrescentar_ignora_pontuacao_do_numero(client):
    cid = _id(client, "substabelecimento", _sub())
    mesmo = {**PROC_A, "numero": " " + PROC_A["numero"] + " "}
    r = client.post(f"/api/documentos/substabelecimento?acrescentar_a={cid}", json=_sub(processos=[mesmo, PROC_C]))
    assert r.json()["processos_novos"] == 1
    assert [p["numero"] for p in _form(cid)["processos"]] == [PROC_A["numero"], PROC_C["numero"]]


def test_cnpj_diferente_cria_novo(client):
    cid = _id(client, "substabelecimento", _sub())
    outro = _sub(outorgante={"razao_social": "OUTRA EMPRESA LTDA", "cnpj": "44.555.666/0001-77"}, processos=[PROC_B])
    novo = _id(client, "substabelecimento", outro)
    assert novo != cid and _todos_substabelecimentos() == 2
    assert client.get("/api/documentos/substabelecimento-existente", params={"documento": "44.555.666/0001-77"}).json()["contract_id"] == novo
    # acrescentar a um substabelecimento de OUTRO outorgante e' recusado
    r = client.post(f"/api/documentos/substabelecimento?acrescentar_a={cid}", json=outro)
    assert r.status_code == 422 and _todos_substabelecimentos() == 2


# ── 3. enviado/assinado nao e' alterado ─────────────────────────────────────


@pytest.mark.parametrize("status", ["assinado", "enviado"])
def test_substabelecimento_assinado_ou_enviado_cria_novo_e_avisa(client, status):
    cid = _id(client, "substabelecimento", _sub())
    _travar(cid, status)
    ex = client.get("/api/documentos/substabelecimento-existente", params={"documento": CNPJ}).json()
    assert ex["existe"] and not ex["pode_acrescentar"] and "assinatura" in ex["motivo"]
    r = client.post(f"/api/documentos/substabelecimento?acrescentar_a={cid}", json=_sub(processos=[PROC_B]))
    assert r.status_code == 200, r.text
    assert r.json()["contract_id"] != cid and "novo substabelecimento" in r.json()["aviso"]
    assert _versao(cid) == 1 and PROC_B["numero"] not in _texto(client, cid)
    assert PROC_B["numero"] in _texto(client, r.json()["contract_id"])


# ── .docx orfao ─────────────────────────────────────────────────────────────


def _docx_no_disco() -> set[str]:
    return {p.name for p in get_generator("distrato").output_dir.glob("*.docx")}


def test_falha_no_segundo_documento_nao_deixa_docx_nem_registro(client, monkeypatch):
    gerador = get_generator("substabelecimento")

    def quebra(*a, **k):
        raise RuntimeError("falha ao gerar o substabelecimento")

    monkeypatch.setattr(gerador, "generate", quebra)
    antes = _docx_no_disco()
    r = _gerar(client, "distrato", DISTRATO)
    assert r.status_code == 500
    assert _docx_no_disco() == antes  # o DOCX do distrato (1o) foi apagado
    assert _derivados_do_origem("distrato") == [] and _derivados_do_origem("substabelecimento") == []


def test_falha_ao_gravar_no_banco_apaga_o_docx(client, monkeypatch):
    from app.database import AuditLogDB
    import app.services.substabelecimento_vinculado as sv

    original = sv.AuditLogDB

    class Quebra:
        def __init__(self, *a, **k):
            raise RuntimeError("falha ao gravar")

    monkeypatch.setattr(sv, "AuditLogDB", Quebra)
    antes = _docx_no_disco()
    r = _gerar(client, "substabelecimento", _sub())
    monkeypatch.setattr(sv, "AuditLogDB", original)
    assert r.status_code == 500 and _docx_no_disco() == antes and _todos_substabelecimentos() == 0


# ── ajustes da revisao da Angela (#143) ─────────────────────────────────────


def _numeros(cid: str) -> list[str]:
    return [p["numero"] for p in _form(cid)["processos"]]


def test_editar_o_distrato_mantem_processo_acrescentado_depois(client, monkeypatch):
    r = _gerar(client, "distrato", DISTRATO)
    distrato, sub = r.json()["contract_id"], r.json()["documentos_gerados_junto"][0]
    partes = {k: _form(sub)[k] for k in ("substabelecentes", "substabelecidos", "endereco_substabelecidos")}
    ac = client.post(f"/api/documentos/substabelecimento?acrescentar_a={sub}", json=_sub(processos=[PROC_C], **partes))
    assert ac.status_code == 200 and _numeros(sub) == [PROC_A["numero"], PROC_C["numero"]]
    # muda outra coisa no distrato: nada some e nao gera versao
    _editar(client, distrato, objeto_contrato_origem="outro objeto")
    assert _numeros(sub) == [PROC_A["numero"], PROC_C["numero"]]
    # distrato passa a ter A e B: B entra, C continua, sem repetir
    novo = {**_form(distrato)["substabelecimento"], "processos": [PROC_A, PROC_B]}
    resp = _editar(client, distrato, substabelecimento=novo)
    assert resp["documentos_regerados"] == [sub]
    assert _numeros(sub) == [PROC_A["numero"], PROC_B["numero"], PROC_C["numero"]]
    # distrato tira o B: B sai (veio do distrato), C (acrescentado) fica
    so_a = {**_form(distrato)["substabelecimento"], "processos": [PROC_A]}
    _editar(client, distrato, substabelecimento=so_a)
    assert _numeros(sub) == [PROC_A["numero"], PROC_C["numero"]]


def test_acrescentar_com_partes_diferentes_da_422_e_nao_muda_o_documento(client):
    cid = _id(client, "substabelecimento", _sub())
    antes, versao = _form(cid), _versao(cid)
    novos = [{"nome": "Outro Patrono", "oab": "OAB/SP sob o n.º 9.999"}]
    for diferente in (
        {"substabelecidos": novos},
        {"substabelecentes": [{**antes["substabelecentes"][0], "nome": "Outra Pessoa"}]},
        {"endereco_substabelecidos": "Rua Nova, 1"},
    ):
        r = client.post(f"/api/documentos/substabelecimento?acrescentar_a={cid}", json=_sub(processos=[PROC_B], **diferente))
        assert r.status_code == 422 and "novo substabelecimento" in r.text
    assert _versao(cid) == versao and _form(cid) == antes
    assert "Outro Patrono" not in _texto(client, cid)


def test_put_do_distrato_com_substab_travado_falha_no_commit_nao_deixa_docx(client, monkeypatch):
    from sqlalchemy.orm import Session

    r = _gerar(client, "distrato", DISTRATO)
    distrato, sub = r.json()["contract_id"], r.json()["documentos_gerados_junto"][0]
    _travar(sub, "assinado")
    antes = _docx_no_disco()
    novo = {**_form(distrato)["substabelecimento"], "processos": [PROC_B]}
    form = {**_form(distrato), "substabelecimento": novo}

    def quebra(self):
        raise RuntimeError("falha no commit")

    monkeypatch.setattr(Session, "commit", quebra)
    resp = client.put(f"/api/contracts/{distrato}", json={"form_data": form})
    monkeypatch.undo()
    assert resp.status_code == 500 and "falha no commit" not in resp.text  # sem detalhe interno
    assert _docx_no_disco() == antes  # o DOCX do substabelecimento novo foi apagado
    assert _todos_substabelecimentos() == 1


def test_distrato_origem_id_inexistente_ou_de_outro_cliente_da_422(client):
    r = client.post("/api/documentos/substabelecimento", json=_sub(distrato_origem_id="nao-existe"))
    assert r.status_code == 422 and _todos_substabelecimentos() == 0
    distrato = _gerar(client, "distrato", DISTRATO).json()["contract_id"]
    outro_cliente = _sub(
        distrato_origem_id=distrato, outorgante={"razao_social": "OUTRA LTDA", "cnpj": "44.555.666/0001-77"},
    )
    antes = _todos_substabelecimentos()
    assert client.post("/api/documentos/substabelecimento", json=outro_cliente).status_code == 422
    assert _todos_substabelecimentos() == antes
    mesmo = _sub(distrato_origem_id=distrato, processos=[PROC_B])
    assert client.post("/api/documentos/substabelecimento", json=mesmo).status_code == 200


def test_acrescentar_sem_mexer_nas_partes_nao_muda_as_partes(client):
    cid = _id(client, "substabelecimento", _sub())
    antes = _form(cid)
    ex = client.get("/api/documentos/substabelecimento-existente", params={"documento": CNPJ}).json()
    # a tela pre-preenche o formulario com as partes do documento existente
    partes = {k: ex[k] for k in ("substabelecentes", "substabelecidos", "endereco_substabelecidos")}
    assert partes["substabelecentes"] == antes["substabelecentes"] and partes["substabelecidos"] == antes["substabelecidos"]
    r = client.post(f"/api/documentos/substabelecimento?acrescentar_a={cid}", json=_sub(processos=[PROC_B], **partes))
    assert r.status_code == 200 and r.json()["processos_novos"] == 1
    depois = _form(cid)
    for k in ("substabelecentes", "substabelecidos", "endereco_substabelecidos"):
        assert depois[k] == antes[k]
    assert [p["numero"] for p in depois["processos"]] == [PROC_A["numero"], PROC_B["numero"]]
