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

Formato fixado: dia com 2 digitos ("05 de outubro de 2026"), como nos modelos.
OAB vai em texto livre e e impressa como veio. Numero de processo e CNJ com
digito verificador; "tipo" do processo e livre (Processo, Agravo de Instrumento...).

Todos os dados sao ficticios (processos com DV valido inventados).
"""
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docx import Document
from fastapi import Request

from app.auth import CurrentUser, _enforce_readonly, get_current_user
from app.database import ColaboradorDB, ContractDB, ContractVersionDB, SessionLocal, utcnow
from app.main import app

SECRET = "test-webhook-secret"
ORIGEM = "origem-001"
SOCIO = {"email": "socia@cf.com", "name": "Sócia CF", "role": "Contratado"}
CONTRATANTE_SIG = {"email": "c@exemplo.com", "name": "Fulano de Tal", "role": "Contratante"}

CLIENTE_PJ = {
    "tipo": "PJ",
    "razao_social": "EMPRESA EXEMPLO LTDA",
    "cnpj": "11.222.333/0001-81",
    "endereco": "Rua Exemplo, 100, Centro, Contagem/MG, CEP 32.000-000",
    "email": "contato@exemplo.com",
    "representantes": [{"nome": "Fulano de Tal", "cpf": "123.456.789-09"}],
}

CLIENTE_PF = {
    "tipo": "PF",
    "nome": "Mônica Exemplo da Silva",
    "nacionalidade": "brasileira",
    "cpf": "987.654.321-00",
    "profissao": "engenheira",
    "estado_civil": "casado",
    "endereco": "Rua das Acácias, 50, Belo Horizonte/MG, CEP 30.100-000",
    "email": "monica@exemplo.com",
}

ADITIVO = {
    "contrato_origem_id": ORIGEM,
    "data_documento": "2026-10-05",
    "data_contrato_origem": "2020-01-15",
    "objeto": "prestação de serviços de auditoria trabalhista",
    "remuneracao": {"valor_mensal": 1250.5, "franquia_horas": 1, "valor_hora_excedente": 210.0},
    "compensacao_anual": True,
    "abrangencia": [{"razao_social": "FILIAL ÁGUA BRANCA LTDA", "cnpj": "44.555.666/0001-77"}],
}

DISTRATO = {
    "contrato_origem_id": ORIGEM,
    "data_documento": "2026-10-07",
    "data_contrato_origem": "2021-03-09",
    "objeto_contrato_origem": "assessoria jurídica empresarial",
    "ressalva_exito": False,
    "substabelecer_e_devolver": True,
}

PROC_A = {"tipo": "Processo", "numero": "1234567-49.2020.8.13.0024",
          "descricao": "Outorgante x Parte Contrária A"}
PROC_B = {"tipo": "Agravo de Instrumento", "numero": "1111111-60.2023.4.06.0000",
          "descricao": "Outorgante x Parte Contrária B"}

SUBSTABELECIMENTO = {
    "contrato_origem_id": None,
    "data_documento": "2026-10-08",
    "outorgante": {"razao_social": "OUTORGANTE EXEMPLO LTDA"},
    "substabelecentes": [
        {"nome": "Sócia CF", "oab": "OAB/MG nº 111.111", "email": "socia@cf.com"},
        {"nome": "Advogado CF", "oab": "OAB/MG nº 222.222", "email": "adv@cf.com"},
    ],
    "substabelecidos": [
        {"nome": "Beltrana Parceira", "genero": "F", "estado_civil": "casada",
         "oab": "OAB/MG sob o nº 333.333"},
        {"nome": "Ciclano Parceiro", "genero": "M", "estado_civil": "solteiro",
         "oab": "OAB/MG sob o nº 444.444"},
    ],
    "endereco_substabelecidos": "Rua Parceira, 10, Belo Horizonte/MG, CEP 30.000-000",
    "processos": [PROC_A, PROC_B],
}


# ── Helpers ───────────────────────────────────────────────────────────────


def _user(role: str = "advogado", email: str = "lawyer@test.com"):
    return lambda: CurrentUser(azure_id="x", email=email, name="Lawyer", role=role)


def _semear_origem(contratante: dict, status: str = "assinado"):
    db = SessionLocal()
    try:
        db.query(ContractVersionDB).filter_by(contract_id=ORIGEM).delete()
        db.query(ContractDB).filter_by(contract_id=ORIGEM).delete()
        db.commit()
        db.add(ContractDB(
            contract_id=ORIGEM, status=status, client_name="Cliente",
            client_email=contratante["email"], current_version=1, created_by="lawyer@test.com",
            created_at=utcnow(), updated_at=utcnow(),
        ))
        db.commit()
        db.add(ContractVersionDB(
            contract_id=ORIGEM, version_number=1,
            form_data_json=json.dumps({"contratantes": [contratante], "escopos": []}),
            created_at=utcnow(),
        ))
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def auth_e_origem():
    app.dependency_overrides[get_current_user] = _user()
    db = SessionLocal()
    try:
        db.add(ColaboradorDB(nome=SOCIO["name"], email=SOCIO["email"], papel="socio", ativo=True))
        db.commit()
    finally:
        db.close()
    _semear_origem(CLIENTE_PJ)
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _gerar(client, tipo: str, payload: dict):
    return client.post(f"/api/documentos/{tipo}", json=payload)


def _id(client, tipo: str, payload: dict) -> str:
    r = _gerar(client, tipo, payload)
    assert r.status_code == 200, r.text
    return r.json()["contract_id"]


def _texto(client, contract_id: str) -> str:
    r = client.get(f"/api/contract/{contract_id}/download")
    assert r.status_code == 200, r.text
    doc = Document(io.BytesIO(r.content))
    partes = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for linha in t.rows:
            partes.extend(c.text for c in linha.cells)
    texto = "\n".join(partes)
    _sem_marcadores(texto)
    return texto


def _sem_marcadores(texto: str):
    """Nenhum documento sai com campo nao preenchido (o modelo real tem '[número de vias]')."""
    for lixo in ("[", "{{", "None", "R$ 0,00", "0 (zero)"):
        assert lixo not in texto, f"marcador solto: {lixo!r}"


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


def _webhook_concluido(client):
    with patch("app.routers.docuseal.DOCUSEAL_WEBHOOK_SECRET", SECRET), \
         patch("app.routers.docuseal._send_participacao_to_financeiro", new_callable=AsyncMock):
        r = client.post("/api/docuseal/webhook",
                        json={"event_type": "submission.completed", "data": {"id": "999"}},
                        headers={"x-docuseal-secret": SECRET})
    assert r.status_code == 200


# ── Pre-preenchimento ─────────────────────────────────────────────────────


def test_prefill_traz_partes_do_contrato_de_origem(client):
    r = client.get(f"/api/documentos/prefill/{ORIGEM}")
    assert r.status_code == 200
    body = r.json()
    assert body["contratantes"][0]["cnpj"] == CLIENTE_PJ["cnpj"]
    assert body["aditivos_existentes"] == 0


# ── Aditivo ───────────────────────────────────────────────────────────────


def test_aditivo_gera_docx_com_partes_valores_e_abrangencia(client):
    texto = _texto(client, _id(client, "aditivo", ADITIVO))

    assert "ADITIVO CONTRATUAL AO CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS" in texto
    assert "º ADITIVO" not in texto  # o 1º aditivo nao leva numero no titulo
    assert "EMPRESA EXEMPLO LTDA" in texto and "11.222.333/0001-81" in texto
    assert "CARVALHO & FURTADO ADVOGADOS" in texto
    assert "prestação de serviços de auditoria trabalhista" in texto
    assert "R$ 1.250,50 (mil, duzentos e cinquenta reais e cinquenta centavos)" in texto
    assert "1 (uma) hora mensal" in texto
    assert "O valor da hora excedente será de R$ 210,00 (duzentos e dez reais)" in texto
    assert "Compensação e Faturamento" in texto and "12 (doze) meses" in texto
    assert "FILIAL ÁGUA BRANCA LTDA" in texto and "44.555.666/0001-77" in texto
    assert "Permanecem inalteradas as demais cláusulas" in texto
    assert "vias de igual teor" in texto
    assert "05 de outubro de 2026" in texto


def test_aditivo_pf_qualifica_com_cpf(client):
    _semear_origem(CLIENTE_PF)
    texto = _texto(client, _id(client, "aditivo", ADITIVO))
    assert "Mônica Exemplo da Silva" in texto and "987.654.321-00" in texto


def test_aditivo_sem_franquia_e_sem_compensacao(client):
    payload = {**ADITIVO, "remuneracao": {"valor_mensal": 1.0}, "compensacao_anual": False,
               "abrangencia": []}
    texto = _texto(client, _id(client, "aditivo", payload))
    assert "R$ 1,00 (um real)" in texto
    assert "franquia" not in texto.lower() and "hora excedente" not in texto
    assert "Compensação e Faturamento" not in texto
    assert "Abrangência" not in texto


def test_aditivo_franquia_no_plural_feminino(client):
    payload = {**ADITIVO, "remuneracao": {**ADITIVO["remuneracao"], "franquia_horas": 2}}
    assert "2 (duas) horas mensais" in _texto(client, _id(client, "aditivo", payload))


def _assinar(contract_id: str):
    """Atalho: o fluxo de assinatura em si e' coberto pelos testes de webhook."""
    db = SessionLocal()
    try:
        db.query(ContractDB).filter_by(contract_id=contract_id).update({"status": "assinado"})
        db.commit()
    finally:
        db.close()


def test_aditivos_seguintes_sao_numerados_e_citam_os_anteriores(client):
    _assinar(_id(client, "aditivo", ADITIVO))
    segundo_id = _id(client, "aditivo", {**ADITIVO, "objeto": "elaboração de políticas internas"})
    segundo = _texto(client, segundo_id)
    _assinar(segundo_id)
    terceiro = _texto(client, _id(client, "aditivo", {**ADITIVO, "objeto": "treinamento de gestores"}))

    assert "2º ADITIVO CONTRATUAL" in segundo
    assert "auditoria trabalhista" in segundo  # considerando do 1º
    assert "3º ADITIVO CONTRATUAL" in terceiro
    assert "auditoria trabalhista" in terceiro and "políticas internas" in terceiro
    assert client.get(f"/api/documentos/prefill/{ORIGEM}").json()["aditivos_existentes"] == 3


def test_aditivo_exige_contrato_de_origem(client):
    assert _gerar(client, "aditivo", {**ADITIVO, "contrato_origem_id": None}).status_code == 422


def test_aditivo_com_origem_inexistente_da_404(client):
    r = _gerar(client, "aditivo", {**ADITIVO, "contrato_origem_id": "nao-existe"})
    assert r.status_code == 404
    assert r.json()["detail"] != "Not Found"  # 404 do contrato, nao de rota inexistente


def test_aditivo_e_assinado_por_contratante_socio_e_testemunhas(client):
    cid = _id(client, "aditivo", ADITIVO)
    papeis = [s["role"] for s in _enviar_capturando(client, cid, [CONTRATANTE_SIG, SOCIO])]
    assert any(p.startswith("Contratante") for p in papeis)
    assert "Contratado" in papeis
    assert any(p.startswith("Testemunha") for p in papeis)


def test_aditivo_assinado_nao_muda_status_da_origem(client):
    cid = _id(client, "aditivo", ADITIVO)
    _enviar_capturando(client, cid, [CONTRATANTE_SIG, SOCIO])
    _webhook_concluido(client)
    assert _status(cid) == "assinado"
    assert _status(ORIGEM) == "assinado"


# ── Distrato ──────────────────────────────────────────────────────────────


def test_distrato_quitacao_total_com_substabelecer(client):
    texto = _texto(client, _id(client, "distrato", DISTRATO))

    assert "DISTRATO AO CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS" in texto
    assert "09 de março de 2021" in texto
    assert "assessoria jurídica empresarial" in texto
    assert "art. 472 do Código Civil" in texto
    assert "integralmente adimplidos" in texto
    assert "honorários de êxito futuros" in texto  # quitacao total
    assert "substabelecer sem reserva de poderes" in texto
    assert "2 (duas) vias" in texto and "2 (duas) testemunhas" in texto
    assert "TESTEMUNHAS" in texto.upper()
    assert "07 de outubro de 2026" in texto
    assert "Aditivo" not in texto  # sem aditivos cadastrados, nao cita nenhum


# Frase da ressalva e PROVISORIA: depende da validacao juridica do socio (issue #126).
RESSALVA = "ressalvados os honorários de êxito"


@pytest.mark.parametrize("ressalva,substabelecer", [
    (True, True), (True, False), (False, False),
])
def test_distrato_flags_sao_independentes(client, ressalva, substabelecer):
    payload = {**DISTRATO, "ressalva_exito": ressalva, "substabelecer_e_devolver": substabelecer}
    texto = _texto(client, _id(client, "distrato", payload))

    assert (RESSALVA in texto) is ressalva
    assert ("honorários de êxito futuros" in texto) is (not ressalva)
    assert ("integralmente adimplidos" in texto) is (not ressalva)
    assert ("substabelecer sem reserva de poderes" in texto) is substabelecer


def test_distrato_cita_so_aditivos_assinados(client):
    # Decisao: aditivo em rascunho conta na numeracao, mas o distrato so cita
    # como "celebrado" o que foi assinado.
    assinado = _id(client, "aditivo", ADITIVO)
    _enviar_capturando(client, assinado, [CONTRATANTE_SIG, SOCIO])
    _webhook_concluido(client)
    _id(client, "aditivo", {**ADITIVO, "objeto": "treinamento de gestores"})  # fica em rascunho

    texto = _texto(client, _id(client, "distrato", DISTRATO))
    assert "auditoria trabalhista" in texto
    assert "treinamento de gestores" not in texto and "2º Aditivo" not in texto


def test_distrato_duplicado_e_bloqueado(client):
    assert _gerar(client, "distrato", DISTRATO).status_code == 200
    assert _gerar(client, "distrato", DISTRATO).status_code == 409


def test_distrato_e_assinado_por_contratante_socio_e_testemunhas(client):
    cid = _id(client, "distrato", DISTRATO)
    papeis = [s["role"] for s in _enviar_capturando(client, cid, [CONTRATANTE_SIG, SOCIO])]
    assert any(p.startswith("Contratante") for p in papeis)
    assert "Contratado" in papeis
    assert any(p.startswith("Testemunha") for p in papeis)


def test_distrato_enviado_mas_nao_assinado_nao_encerra_origem(client):
    cid = _id(client, "distrato", DISTRATO)
    _enviar_capturando(client, cid, [CONTRATANTE_SIG, SOCIO])
    assert _status(ORIGEM) == "assinado"


def test_distrato_assinado_encerra_o_contrato_de_origem(client):
    cid = _id(client, "distrato", DISTRATO)
    _enviar_capturando(client, cid, [CONTRATANTE_SIG, SOCIO])
    _webhook_concluido(client)
    assert _status(cid) == "assinado"
    assert _status(ORIGEM) == "encerrado"


# ── Substabelecimento ─────────────────────────────────────────────────────


def test_substabelecimento_sem_origem_lista_processos_e_advogados(client):
    texto = _texto(client, _id(client, "substabelecimento", SUBSTABELECIMENTO))

    assert "SUBSTABELECIMENTO SEM RESERVA DE PODERES" in texto
    assert "SÓCIA CF, OAB/MG nº 111.111" in texto  # substabelecentes em MAIUSCULAS
    assert "ADVOGADO CF, OAB/MG nº 222.222" in texto
    assert "substabelecem, SEM RESERVA DE PODERES" in texto
    assert "Dra. Beltrana Parceira, brasileira, casada, inscrita na OAB/MG sob o nº 333.333" in texto
    assert "Dr. Ciclano Parceiro, brasileiro, solteiro, inscrito na OAB/MG sob o nº 444.444" in texto
    assert "Rua Parceira, 10, Belo Horizonte/MG, CEP 30.000-000" in texto
    assert "OUTORGANTE EXEMPLO LTDA" in texto
    assert "seus incidentes, desdobramentos e recursos correlatos" in texto
    assert "ressalvados os honorários contratuais e sucumbenciais" in texto
    assert "Processo n.º 1234567-49.2020.8.13.0024" in texto and "Parte Contrária A" in texto
    assert "Agravo de Instrumento n.º 1111111-60.2023.4.06.0000" in texto and "Parte Contrária B" in texto
    assert "25.463.159/0001-73" in texto  # extensao fixa a patronos anteriores
    assert "08 de outubro de 2026" in texto


def test_substabelecimento_com_um_processo(client):
    texto = _texto(client, _id(client, "substabelecimento", {**SUBSTABELECIMENTO, "processos": [PROC_A]}))
    assert "1234567-49.2020.8.13.0024" in texto and "1111111-60.2023.4.06.0000" not in texto


@pytest.mark.parametrize("numero", [
    "123",                          # formato invalido
    "1234567-50.2020.8.13.0024",    # digito verificador errado
])
def test_substabelecimento_rejeita_numero_de_processo_invalido(client, numero):
    payload = {**SUBSTABELECIMENTO, "processos": [{**PROC_A, "numero": numero}]}
    assert _gerar(client, "substabelecimento", payload).status_code == 422


@pytest.mark.parametrize("campo", ["processos", "substabelecentes", "substabelecidos"])
def test_substabelecimento_exige_listas_nao_vazias(client, campo):
    assert _gerar(client, "substabelecimento", {**SUBSTABELECIMENTO, campo: []}).status_code == 422


def test_substabelecimento_e_assinado_so_pelos_substabelecentes(client):
    sid = _id(client, "substabelecimento", SUBSTABELECIMENTO)
    enviados = _enviar_capturando(client, sid, [
        {"email": "socia@cf.com", "name": "Sócia CF", "role": "Substabelecente"},
        {"email": "adv@cf.com", "name": "Advogado CF", "role": "Substabelecente"},
    ])
    papeis = [s["role"] for s in enviados]
    assert not any(p.startswith("Testemunha") for p in papeis)
    assert not any(p.startswith("Contratante") for p in papeis)
    assert {s["email"] for s in enviados} == {"socia@cf.com", "adv@cf.com"}


# ── Vinculo, listagem e acesso ────────────────────────────────────────────


def test_documentos_derivados_aparecem_no_contrato_de_origem(client):
    _id(client, "aditivo", ADITIVO)
    _id(client, "distrato", DISTRATO)
    r = client.get(f"/api/contracts/{ORIGEM}/documentos")
    assert r.status_code == 200
    tipos = sorted(d["tipo_contrato"] for d in r.json()["documentos"])
    assert tipos == ["aditivo", "distrato"]


def test_edicao_de_rascunho_regenera_nova_versao(client):
    # Amarra o formato salvo: form_data usa as mesmas chaves do payload.
    cid = _id(client, "aditivo", ADITIVO)
    form = client.get(f"/api/contracts/{cid}/form-data").json()["form_data"]
    form["objeto"] = "objeto corrigido"
    assert client.put(f"/api/contracts/{cid}", json={"form_data": form}).status_code == 200
    assert "objeto corrigido" in _texto(client, cid)
    assert client.get(f"/api/contracts/{cid}").json()["current_version"] == 2


def _origem_de_outro_advogado():
    db = SessionLocal()
    try:
        db.query(ContractDB).filter_by(contract_id=ORIGEM).update({"created_by": "outro@test.com"})
        db.commit()
    finally:
        db.close()


def test_advogado_nao_acessa_contrato_alheio(client):
    _origem_de_outro_advogado()
    assert _gerar(client, "aditivo", ADITIVO).status_code == 403
    assert client.get(f"/api/documentos/prefill/{ORIGEM}").status_code == 403  # expoe CPF/CNPJ
    assert client.get(f"/api/contracts/{ORIGEM}/documentos").status_code == 403


def test_admin_acessa_contrato_alheio(client):
    _origem_de_outro_advogado()
    app.dependency_overrides[get_current_user] = _user("admin", "admin@test.com")
    assert client.get(f"/api/documentos/prefill/{ORIGEM}").status_code == 200
    assert _gerar(client, "aditivo", ADITIVO).status_code == 200


def test_leitor_nao_cria_documento(client):
    # O override pula o guard de somente-leitura; aqui ele e aplicado de verdade,
    # provando que o router novo depende de get_current_user.
    def leitor(request: Request):
        return _enforce_readonly(request, CurrentUser(azure_id="x", email="l@test.com",
                                                      name="Leitor", role="leitor"))

    app.dependency_overrides[get_current_user] = leitor
    assert _gerar(client, "aditivo", ADITIVO).status_code == 403


def test_tipo_desconhecido_da_404(client):
    r = _gerar(client, "procuracao", ADITIVO)
    assert r.status_code == 404
    assert "procuracao" in r.json()["detail"]  # 404 do tipo, nao de rota inexistente


# ── Ajustes da revisao do PR #127 ─────────────────────────────────────────


def test_distrato_com_pessoa_fisica_nao_fala_em_contrato_social(client):
    _semear_origem(CLIENTE_PF)
    texto = _texto(client, _id(client, "distrato", DISTRATO))
    assert 'doravante denominado(a) simplesmente "CONTRATANTE"' in texto
    assert "inscrito(a)" not in texto
    assert texto.count("Contrato Social") == 1  # so' o do escritorio (CONTRATADA)


def _data_do_contrato_na_origem(iso: str):
    db = SessionLocal()
    try:
        ver = db.query(ContractVersionDB).filter_by(contract_id=ORIGEM).one()
        form = json.loads(ver.form_data_json)
        form["data_contrato_origem"] = iso
        ver.form_data_json = json.dumps(form)
        db.commit()
    finally:
        db.close()


# Decisao do usuario: data do contrato de origem e' OBRIGATORIA no aditivo e no
# distrato, para nao sair considerando sem ano nem com ano errado.
@pytest.mark.parametrize("tipo,payload", [("aditivo", ADITIVO), ("distrato", DISTRATO)])
def test_data_do_contrato_de_origem_e_obrigatoria(client, tipo, payload):
    sem = {k: v for k, v in payload.items() if k != "data_contrato_origem"}
    assert _gerar(client, tipo, sem).status_code == 422
    assert _gerar(client, tipo, {**payload, "data_contrato_origem": None}).status_code == 422


def test_aditivo_cita_o_ano_informado(client):
    assert "Serviços Advocatícios em 2020;" in _texto(client, _id(client, "aditivo", ADITIVO))


def test_prefill_sugere_a_data_do_contrato_do_pai(client):
    assert client.get(f"/api/documentos/prefill/{ORIGEM}").json()["data_contrato_origem"] is None
    _data_do_contrato_na_origem("2019-05-02")
    assert client.get(f"/api/documentos/prefill/{ORIGEM}").json()["data_contrato_origem"] == "2019-05-02"


def test_aditivo_prefere_a_data_informada_pelo_advogado(client):
    _data_do_contrato_na_origem("2019-05-02")
    texto = _texto(client, _id(client, "aditivo", ADITIVO))
    assert "Serviços Advocatícios em 2020;" in texto and "2019" not in texto


@pytest.mark.parametrize("tipo,payload,campo", [
    ("aditivo", ADITIVO, "data_documento"),
    ("distrato", DISTRATO, "data_documento"),
    ("distrato", DISTRATO, "data_contrato_origem"),
    ("aditivo", ADITIVO, "data_contrato_origem"),
    ("substabelecimento", SUBSTABELECIMENTO, "data_documento"),
])
def test_data_invalida_da_422(client, tipo, payload, campo):
    assert _gerar(client, tipo, {**payload, campo: "2026-13-45"}).status_code == 422


def test_substabelecimento_com_um_substabelecente_e_uma_substabelecida(client):
    payload = {**SUBSTABELECIMENTO, "substabelecentes": SUBSTABELECIMENTO["substabelecentes"][:1],
               "substabelecidos": SUBSTABELECIMENTO["substabelecidos"][:1]}
    texto = _texto(client, _id(client, "substabelecimento", payload))
    assert "OAB/MG nº 111.111, substabelece, SEM RESERVA DE PODERES, à advogada Dra. Beltrana" in texto
    assert "substabelecem" not in texto and "todos com" not in texto
    assert "com endereço profissional à Rua Parceira" in texto


def test_substabelecimento_com_um_substabelecido_homem(client):
    payload = {**SUBSTABELECIMENTO, "substabelecidos": SUBSTABELECIMENTO["substabelecidos"][1:]}
    texto = _texto(client, _id(client, "substabelecimento", payload))
    assert "substabelecem, SEM RESERVA DE PODERES, ao advogado Dr. Ciclano" in texto


def test_substabelecimento_com_varios_continua_no_plural(client):
    texto = _texto(client, _id(client, "substabelecimento", SUBSTABELECIMENTO))
    assert "aos advogados Dra. Beltrana" in texto and "todos com endereço profissional" in texto


def test_distrato_com_ressalva_nao_contradiz_a_quitacao(client):
    texto = _texto(client, _id(client, "distrato", {**DISTRATO, "ressalva_exito": True,
                                                    "substabelecer_e_devolver": False}))
    assert "plena, geral, rasa" not in texto
    assert texto.index("em juízo ou fora dele") < texto.index(RESSALVA)  # qualifica a quitacao
    assert "DA QUITAÇÃO" in texto and "REVOGAÇÃO DE PODERES" not in texto


def test_distrato_total_mantem_a_quitacao_plena_e_o_titulo_de_poderes(client):
    texto = _texto(client, _id(client, "distrato", DISTRATO))
    assert "plena, geral, rasa, irrestrita e irrevogável quitação, em juízo ou fora dele" in texto
    assert "DA QUITAÇÃO E REVOGAÇÃO DE PODERES" in texto


def test_edicao_nao_troca_o_contrato_de_origem(client):
    cid = _id(client, "aditivo", ADITIVO)
    form = client.get(f"/api/contracts/{cid}/form-data").json()["form_data"]
    form["contrato_origem_id"] = "outro-contrato"
    assert client.put(f"/api/contracts/{cid}", json={"form_data": form}).status_code == 200
    atual = client.get(f"/api/contracts/{cid}/form-data").json()["form_data"]
    assert atual["contrato_origem_id"] == ORIGEM
    assert [d["contract_id"] for d in client.get(f"/api/contracts/{ORIGEM}/documentos").json()["documentos"]] == [cid]


# ── Revisao final (Angela, PR #127) ───────────────────────────────────────


def test_aditivo_cita_so_aditivos_assinados_mas_numera_os_rascunhos(client):
    _assinar(_id(client, "aditivo", ADITIVO))
    _id(client, "aditivo", {**ADITIVO, "objeto": "elaboração de políticas internas"})  # rascunho
    texto = _texto(client, _id(client, "aditivo", {**ADITIVO, "objeto": "treinamento de gestores"}))
    assert "3º ADITIVO CONTRATUAL" in texto
    assert "firmaram o 1º Aditivo" in texto
    assert "políticas internas" not in texto and "2º Aditivo" not in texto


@pytest.mark.parametrize("data", ["20261016", "2026-W42-1", "2026-10-16T10:00", " 2026-10-16"])
def test_data_fora_do_formato_aaaa_mm_dd_da_422(client, data):
    assert _gerar(client, "aditivo", {**ADITIVO, "data_documento": data}).status_code == 422


def test_substabelecimento_um_substabelecente_varios_substabelecidos(client):
    payload = {**SUBSTABELECIMENTO, "substabelecentes": SUBSTABELECIMENTO["substabelecentes"][:1]}
    texto = _texto(client, _id(client, "substabelecimento", payload))
    assert "OAB/MG nº 111.111, substabelece, SEM RESERVA DE PODERES, aos advogados" in texto
    assert "substabelecem" not in texto and "todos com endereço profissional" in texto
