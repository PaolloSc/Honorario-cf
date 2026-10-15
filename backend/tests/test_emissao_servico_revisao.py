"""Ajustes da revisao da #122: 5xx nao e rejeicao, consulta sem emissor ativo, SEM_NOTA so manual em producao."""
from __future__ import annotations

import datetime

import httpx
from sqlalchemy import text

from app.database import SessionLocal
from app.models.emissao_db import NfseEmitidaDB
from tests.test_emissao_servico import (  # noqa: F401  (fixtures e helpers compartilhados)
    CHAVE, _ambiente, _cenario, _emitir, _fatura, _sem_resposta, _status_fatura, client, sefin,
)


def test_5xx_com_corpo_de_erro_nao_e_rejeicao_e_nao_libera_nova_dps(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    sefin.post_resp = lambda req: httpx.Response(500, json={"erros": [{"Codigo": "E1000", "Descricao": "falha interna"}]})
    j = _emitir(client, f["id"], "k1").json()
    assert (j["status"], j["erro_codigo"]) == ("processando", None)
    assert _status_fatura(f["id"]) == "emitindo"
    ev = client.get(f"/api/nfse-emitidas/{j['id']}").json()["eventos"]
    assert ev[-1]["payload"]["erros"][0]["codigo"] == "E1000"  # o erro fica registrado
    _emitir(client, f["id"], "k2")  # outra tentativa nao gera outra DPS: so consulta
    assert len(sefin.posts) == 1


def test_4xx_com_erro_continua_sendo_rejeicao(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    sefin.post_resp = lambda req: httpx.Response(422, json={"erros": [{"Codigo": "E0001", "Descricao": "x"}]})
    assert _emitir(client, f["id"]).json()["status"] == "rejeitada"


def _com_nota_processando(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    _sem_resposta(sefin)
    j = _emitir(client, f["id"]).json()
    sefin.get_dps_resp = lambda req: httpx.Response(200, json={"chaveAcesso": CHAVE[3:]})
    return f, j


def _sql(comando: str) -> None:
    with SessionLocal() as db:
        db.execute(text(comando))
        db.commit()


def test_consulta_funciona_com_o_emissor_desativado(client, sefin):
    f, j = _com_nota_processando(client, sefin)
    _sql("UPDATE emissor_config SET ativo = FALSE")
    r = client.post(f"/api/nfse-emitidas/{j['id']}/consultar")
    assert r.status_code == 200 and r.json()["status"] == "autorizada"
    assert _status_fatura(f["id"]) == "emitida"


def test_consulta_exige_certificado_do_prestador_da_nota(client, sefin):
    f, j = _com_nota_processando(client, sefin)
    _sql("UPDATE nfse_emitidas SET cnpj_prestador='11222333000181'")  # nota de outro prestador
    r = client.post(f"/api/nfse-emitidas/{j['id']}/consultar")
    assert r.status_code == 409 and "prestador desta nota" in r.json()["detail"]
    _sql("UPDATE emissor_config SET cert_pfx_enc = NULL")
    assert client.post(f"/api/nfse-emitidas/{j['id']}/consultar").status_code == 409


def test_consulta_usa_o_municipio_da_emissao_nao_o_da_configuracao_atual(client, sefin):
    f, j = _com_nota_processando(client, sefin)
    _sql("UPDATE emissor_config SET municipio_ibge='3550308'")
    client.post(f"/api/nfse-emitidas/{j['id']}/consultar")
    assert any("DPS3106200" in g for g in sefin.gets) and not any("DPS3550308" in g for g in sefin.gets)


def test_sem_nota_em_producao_so_com_confirmacao_manual(client, sefin):
    s, t = _cenario(client)
    f = _fatura(client, s, t)
    _sem_resposta(sefin)
    j = _emitir(client, f["id"]).json()
    with SessionLocal() as db:  # nota de producao, ja velha
        n = db.get(NfseEmitidaDB, j["id"])
        n.criado_em = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30)
        n.ambiente = "producao"
        db.commit()
    sefin.get_dps_resp = lambda req: httpx.Response(404, json={"erros": [{"Codigo": "E2404", "Descricao": "nao ha"}]})
    assert client.post(f"/api/nfse-emitidas/{j['id']}/consultar").json()["status"] == "processando"  # nao conclui sozinho
    r = client.post(f"/api/nfse-emitidas/{j['id']}/consultar?confirmar_sem_nota=true").json()
    assert (r["status"], r["erro_codigo"]) == ("rejeitada", "SEM_NOTA")
    assert _status_fatura(f["id"]) == "aprovada"


def test_confirmacao_manual_nao_vale_quando_a_nota_existe_no_sefin(client, sefin):
    f, j = _com_nota_processando(client, sefin)  # GET /dps devolve a chave
    r = client.post(f"/api/nfse-emitidas/{j['id']}/consultar?confirmar_sem_nota=true").json()
    assert r["status"] == "autorizada"
