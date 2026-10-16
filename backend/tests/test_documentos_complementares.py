"""Aceitacao da issue #126: aditivo, distrato e substabelecimento na plataforma.

Testes escritos ANTES da implementacao — todos falham ate a feature existir.
Um seam so: a API HTTP. Gera o documento, baixa o .docx e confere o texto;
envia para assinatura com o DocuSeal mockado; simula o webhook do distrato.

Contrato de API fixado por estes testes:
  POST /api/documentos/{tipo}              tipo in aditivo|distrato|substabelecimento
       -> {success, contract_id, download_url}
  GET  /api/documentos/prefill/{contrato_origem_id}
       -> {contratantes, aditivos_existentes}
  GET  /api/contracts/{contract_id}/documentos
       -> {documentos: [{contract_id, tipo_contrato, status}]}
"""
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docx import Document

from app.auth import CurrentUser, get_current_user
from app.database import ColaboradorDB, ContractDB, ContractVersionDB, SessionLocal, utcnow
from app.main import app

SECRET = "test-webhook-secret"
ORIGEM = "origem-001"
SOCIO = {"email": "socia@cf.com", "name": "Socia CF", "role": "Contratado"}

# Dados ficticios — nunca os dos modelos reais.
CLIENTE_PJ = {
    "tipo": "PJ",
    "razao_social": "EMPRESA EXEMPLO LTDA",
    "cnpj": "11.222.333/0001-81",
    "endereco": "Rua Exemplo, 100, Centro, Contagem/MG, CEP 32.000-000",
    "email": "contato@exemplo.com",
    "representantes": [{"nome": "Fulano de Tal", "cpf": "123.456.789-09"}],
}

ADITIVO = {
    "contrato_origem_id": ORIGEM,
    "data_documento": "2026-10-16",
    "objeto": "prestacao de servicos de compliance trabalhista",
    "remuneracao": {"valor_mensal": 1500.0, "franquia_horas": 5, "valor_hora_excedente": 300.0},
    "compensacao_anual": True,
    "abrangencia": [{"razao_social": "FILIAL EXEMPLO LTDA", "cnpj": "44.555.666/0001-77"}],
}

DISTRATO = {
    "contrato_origem_id": ORIGEM,
    "data_documento": "2026-10-16",
    "data_contrato_origem": "2022-04-28",
    "objeto_contrato_origem": "consultoria e contencioso de rotina",
    "ressalva_exito": False,
    "substabelecer_e_devolver": True,
}

SUBSTABELECIMENTO = {
    "contrato_origem_id": None,
    "data_documento": "2026-10-16",
    "outorgante": {"razao_social": "OUTORGANTE EXEMPLO LTDA"},
    "substabelecentes": [
        {"nome": "Socia CF", "oab": "OAB/MG n.º 111.111", "email": "socia@cf.com"},
        {"nome": "Advogado CF", "oab": "OAB/MG n.º 222.222", "email": "adv@cf.com"},
    ],
    "substabelecidos": [
        {"nome": "Beltrana Parceira", "genero": "F", "estado_civil": "casada",
         "oab": "OAB/MG sob o n.º 333.333"},
    ],
    "endereco_substabelecidos": "Rua Parceira, 10, Belo Horizonte/MG, CEP 30.000-000",
    "processos": [
        {"numero": "5012442-37.2017.8.13.0079", "descricao": "Outorgante x Parte Contraria A"},
        {"numero": "0864562-85.2014.8.13.0024", "descricao": "Outorgante x Parte Contraria B"},
    ],
}


# ── Helpers ───────────────────────────────────────────────────────────────


def _user(role: str = "advogado"):
    return lambda: CurrentUser(azure_id="x", email="lawyer@test.com", name="Lawyer", role=role)


@pytest.fixture(autouse=True)
def auth_e_origem():
    app.dependency_overrides[get_current_user] = _user()
    db = SessionLocal()
    try:
        db.add(ColaboradorDB(nome=SOCIO["name"], email=SOCIO["email"], papel="socio", ativo=True))
        db.add(ContractDB(
            contract_id=ORIGEM, status="assinado", client_name=CLIENTE_PJ["razao_social"],
            client_email=CLIENTE_PJ["email"], current_version=1, created_by="lawyer@test.com",
            created_at=utcnow(), updated_at=utcnow(),
        ))
        db.commit()
        db.add(ContractVersionDB(
            contract_id=ORIGEM, version_number=1,
            form_data_json=json.dumps({"contratantes": [CLIENTE_PJ], "escopos": []}),
            created_at=utcnow(),
        ))
        db.commit()
    finally:
        db.close()
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _gerar(client, tipo: str, payload: dict):
    return client.post(f"/api/documentos/{tipo}", json=payload)


def _texto(client, contract_id: str) -> str:
    r = client.get(f"/api/contract/{contract_id}/download")
    assert r.status_code == 200, r.text
    doc = Document(io.BytesIO(r.content))
    partes = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for linha in t.rows:
            partes.extend(c.text for c in linha.cells)
    return "\n".join(partes)


def _status(contract_id: str) -> str:
    db = SessionLocal()
    try:
        return db.query(ContractDB).filter_by(contract_id=contract_id).one().status
    finally:
        db.close()


def _enviar_capturando(client, contract_id: str, signatarios: list[dict]) -> list[dict]:
    capturados: list[dict] = []

    async def capture(template_id, signatarios, send_email=True):
        capturados.extend(signatarios)
        return {"success": True, "submission": {"id": 999, "submitters": []}, "message": "ok"}

    svc = MagicMock()
    svc.create_template_from_docx = AsyncMock(return_value={"id": 1, "name": "T"})
    svc.send_for_signature = AsyncMock(side_effect=capture)
    with patch("app.routers.docuseal.get_docuseal_service", return_value=svc), \
         patch("app.routers.docuseal._send_contract_to_financeiro", new_callable=AsyncMock), \
         patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
        r = client.post("/api/docuseal/send-for-signature",
                        json={"contract_id": contract_id, "signatarios": signatarios})
    assert r.status_code == 200, r.text
    return capturados


# ── Pre-preenchimento ─────────────────────────────────────────────────────


def test_prefill_traz_partes_do_contrato_de_origem(client):
    r = client.get(f"/api/documentos/prefill/{ORIGEM}")
    assert r.status_code == 200
    body = r.json()
    assert body["contratantes"][0]["cnpj"] == CLIENTE_PJ["cnpj"]
    assert body["aditivos_existentes"] == 0


# ── Aditivo ───────────────────────────────────────────────────────────────


def test_aditivo_gera_docx_com_partes_valores_e_abrangencia(client):
    r = _gerar(client, "aditivo", ADITIVO)
    assert r.status_code == 200, r.text
    texto = _texto(client, r.json()["contract_id"])

    assert "ADITIVO CONTRATUAL AO CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS" in texto
    assert "EMPRESA EXEMPLO LTDA" in texto and "11.222.333/0001-81" in texto
    assert "CARVALHO & FURTADO ADVOGADOS" in texto
    assert "R$ 1.500,00 (mil e quinhentos reais)" in texto
    assert "5 (cinco) horas" in texto
    assert "R$ 300,00 (trezentos reais)" in texto
    assert "FILIAL EXEMPLO LTDA" in texto and "44.555.666/0001-77" in texto
    assert "Permanecem inalteradas as demais cláusulas" in texto
    assert "16 de outubro de 2026" in texto


def test_segundo_aditivo_e_numerado_e_cita_o_primeiro(client):
    primeiro = _gerar(client, "aditivo", ADITIVO).json()["contract_id"]
    r = _gerar(client, "aditivo", {**ADITIVO, "objeto": "elaboracao de politicas internas"})
    assert r.status_code == 200, r.text
    texto = _texto(client, r.json()["contract_id"])

    assert "2º ADITIVO CONTRATUAL" in texto
    assert "compliance trabalhista" in texto  # considerando do 1º aditivo
    assert client.get(f"/api/documentos/prefill/{ORIGEM}").json()["aditivos_existentes"] == 2
    assert primeiro != r.json()["contract_id"]


def test_aditivo_exige_contrato_de_origem(client):
    r = _gerar(client, "aditivo", {**ADITIVO, "contrato_origem_id": None})
    assert r.status_code == 422


def test_aditivo_com_origem_inexistente_da_404(client):
    r = _gerar(client, "aditivo", {**ADITIVO, "contrato_origem_id": "nao-existe"})
    assert r.status_code == 404
    assert r.json()["detail"] != "Not Found"  # 404 do contrato, nao de rota inexistente


# ── Distrato ──────────────────────────────────────────────────────────────


def test_distrato_gera_quitacao_total_e_clausula_de_substabelecer(client):
    r = _gerar(client, "distrato", DISTRATO)
    assert r.status_code == 200, r.text
    texto = _texto(client, r.json()["contract_id"])

    assert "DISTRATO AO CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS" in texto
    assert "28 de abril de 2022" in texto
    assert "art. 472 do Código Civil" in texto
    assert "honorários de êxito futuros" in texto  # quitacao total
    assert "substabelecer sem reserva de poderes" in texto
    assert "TESTEMUNHAS" in texto.upper()


def test_distrato_com_ressalva_de_exito_e_sem_substabelecer(client):
    r = _gerar(client, "distrato", {**DISTRATO, "ressalva_exito": True,
                                    "substabelecer_e_devolver": False})
    assert r.status_code == 200, r.text
    texto = _texto(client, r.json()["contract_id"])

    assert "ressalvados os honorários de êxito" in texto
    assert "substabelecer sem reserva de poderes" not in texto


def test_distrato_cita_aditivos_existentes(client):
    _gerar(client, "aditivo", ADITIVO)
    texto = _texto(client, _gerar(client, "distrato", DISTRATO).json()["contract_id"])
    assert "aditivo" in texto.lower()


def test_distrato_duplicado_e_bloqueado(client):
    assert _gerar(client, "distrato", DISTRATO).status_code == 200
    assert _gerar(client, "distrato", DISTRATO).status_code == 409


def test_distrato_assinado_encerra_o_contrato_de_origem(client):
    distrato_id = _gerar(client, "distrato", DISTRATO).json()["contract_id"]
    _enviar_capturando(client, distrato_id, [
        {"email": "c@exemplo.com", "name": "Fulano de Tal", "role": "Contratante"}, SOCIO,
    ])
    with patch("app.routers.docuseal.DOCUSEAL_WEBHOOK_SECRET", SECRET), \
         patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
        r = client.post("/api/docuseal/webhook",
                        json={"event_type": "submission.completed", "data": {"id": "999"}},
                        headers={"x-docuseal-secret": SECRET})
    assert r.status_code == 200
    assert _status(distrato_id) == "assinado"
    assert _status(ORIGEM) == "encerrado"


# ── Substabelecimento ─────────────────────────────────────────────────────


def test_substabelecimento_sem_origem_lista_processos_e_advogados(client):
    r = _gerar(client, "substabelecimento", SUBSTABELECIMENTO)
    assert r.status_code == 200, r.text
    texto = _texto(client, r.json()["contract_id"])

    assert "SUBSTABELECIMENTO SEM RESERVA DE PODERES" in texto
    assert "SOCIA CF, OAB/MG n.º 111.111" in texto.upper()
    assert "Beltrana Parceira, brasileira, casada" in texto
    assert "OUTORGANTE EXEMPLO LTDA" in texto
    assert "5012442-37.2017.8.13.0079" in texto and "0864562-85.2014.8.13.0024" in texto
    assert "ressalvados os honorários contratuais e sucumbenciais" in texto
    assert "25.463.159/0001-73" in texto  # extensao fixa a patronos anteriores


def test_substabelecimento_rejeita_numero_de_processo_invalido(client):
    payload = {**SUBSTABELECIMENTO, "processos": [{"numero": "123", "descricao": "x"}]}
    assert _gerar(client, "substabelecimento", payload).status_code == 422


def test_substabelecimento_e_assinado_so_pelos_substabelecentes(client):
    sid = _gerar(client, "substabelecimento", SUBSTABELECIMENTO).json()["contract_id"]
    enviados = _enviar_capturando(client, sid, [
        {"email": "socia@cf.com", "name": "Socia CF", "role": "Substabelecente"},
        {"email": "adv@cf.com", "name": "Advogado CF", "role": "Substabelecente"},
    ])
    papeis = [s["role"] for s in enviados]
    assert not any(p.startswith("Testemunha") for p in papeis)
    assert not any(p.startswith("Contratante") for p in papeis)
    assert {s["email"] for s in enviados} == {"socia@cf.com", "adv@cf.com"}


# ── Vinculo, listagem e acesso ────────────────────────────────────────────


def test_documentos_derivados_aparecem_no_contrato_de_origem(client):
    _gerar(client, "aditivo", ADITIVO)
    _gerar(client, "distrato", DISTRATO)
    r = client.get(f"/api/contracts/{ORIGEM}/documentos")
    assert r.status_code == 200
    tipos = sorted(d["tipo_contrato"] for d in r.json()["documentos"])
    assert tipos == ["aditivo", "distrato"]


def test_edicao_de_rascunho_regenera_nova_versao(client):
    cid = _gerar(client, "aditivo", ADITIVO).json()["contract_id"]
    form = client.get(f"/api/contracts/{cid}/form-data").json()["form_data"]
    form["objeto"] = "objeto corrigido"
    assert client.put(f"/api/contracts/{cid}", json={"form_data": form}).status_code == 200
    assert "objeto corrigido" in _texto(client, cid)
    assert client.get(f"/api/contracts/{cid}").json()["current_version"] == 2


def test_advogado_nao_cria_documento_de_contrato_alheio(client):
    db = SessionLocal()
    try:
        db.query(ContractDB).filter_by(contract_id=ORIGEM).update({"created_by": "outro@test.com"})
        db.commit()
    finally:
        db.close()
    assert _gerar(client, "aditivo", ADITIVO).status_code == 403


def test_tipo_desconhecido_da_404(client):
    r = _gerar(client, "procuracao", ADITIVO)
    assert r.status_code == 404
    assert "procuracao" in r.json()["detail"]  # 404 do tipo, nao de rota inexistente
