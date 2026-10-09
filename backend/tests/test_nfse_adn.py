"""NFS-e do Padrao Nacional (ADN): parser, worker de distribuicao e ingest.

Sem rede: o ADN e simulado com httpx.MockTransport e o certificado e um .pfx
autoassinado gerado no teste. Fixtures XML feitas a mao a partir do XSD v1.01."""
import base64
import gzip
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from tests.test_nfse_sync_orchestrator import db  # noqa: F401 -- fixture

FIXTURES = Path(__file__).parent / "fixtures" / "nfse"
CF = "25463159000173"
CHAVE_EMITIDA = "31062002254631590001730000000000000126100000000017"


def _xml(nome: str) -> bytes:
    return (FIXTURES / nome).read_bytes()


# --- parser -----------------------------------------------------------------

def test_nacional_emitida_le_valores_e_retencoes():
    from app.services.nfse_parser import parse_documento

    nf = parse_documento(_xml("nacional_emitida.xml"), CF)
    assert (nf.direcao, nf.chave_acesso, nf.numero, nf.serie) == ("emitida", CHAVE_EMITIDA, "12", None)
    assert nf.cnpj_prestador == CF and nf.tomador_doc == "98765432000100"
    assert (nf.competencia, nf.data_emissao) == (date(2026, 5, 1), date(2026, 5, 10))
    assert nf.discriminacao == "Honorarios advocaticios maio/2026"
    assert (nf.iss_retido, nf.irrf, nf.pis, nf.cofins, nf.csll) == (
        Decimal("500.00"), Decimal("150.00"), Decimal("65.00"), Decimal("300.00"), Decimal("100.00"))
    assert nf.valor_liquido == Decimal("8885.00")  # = vLiq do XML


def test_nacional_recebida_sem_retencao():
    from app.services.nfse_parser import parse_documento

    nf = parse_documento(_xml("nacional_recebida.xml"), CF)
    assert nf.direcao == "recebida" and nf.cnpj_prestador == "11222333000144"
    assert nf.tomador_doc == CF
    # tpRetISSQN=1 e tpRetPisCofins=2: ISS, PIS e COFINS existem mas nao sao retidos.
    assert nf.valor_liquido == nf.valor_servicos == Decimal("2000.00")


def test_nacional_emitente_pessoa_fisica():
    from app.services.nfse_parser import parse_documento

    xml = _xml("nacional_recebida.xml").replace(b"<CNPJ>11222333000144</CNPJ>", b"<CPF>12345678909</CPF>")
    nf = parse_documento(xml, CF)
    assert nf.cnpj_prestador == "12345678909" and nf.direcao == "recebida"


def test_evento_de_cancelamento():
    from app.models.nfse import CancelamentoData
    from app.services.nfse_parser import parse_documento

    ev = parse_documento(_xml("nacional_evento_cancelamento.xml"), CF)
    assert isinstance(ev, CancelamentoData)
    assert ev.chave_acesso == CHAVE_EMITIDA
    assert ev.data_cancelamento == datetime(2026, 5, 12, 13, 58, tzinfo=timezone(timedelta(hours=-3)))


def test_evento_que_nao_cancela_e_ignorado():
    from app.services.nfse_parser import parse_documento

    xml = _xml("nacional_evento_cancelamento.xml").replace(b"e101101", b"e202201")
    assert parse_documento(xml, CF) is None


def test_abrasf_continua_passando_pelo_parser_antigo():
    from app.services.nfse_parser import parse_documento

    nf = parse_documento(_xml("abrasf_minimo.xml"), CF)
    assert nf.numero == "1000" and nf.direcao == "emitida" and nf.chave_acesso is None


@pytest.mark.parametrize("nome", ["abrasf_malformado.xml", "xxe_attack.xml"])
def test_xml_invalido_ou_xxe_falha(nome):
    from app.services.nfse_parser import NFSeParseError, parse_documento

    with pytest.raises(NFSeParseError):
        parse_documento(_xml(nome), CF)


def test_nacional_sem_chave_falha():
    from app.services.nfse_parser import NFSeParseError, parse_documento

    with pytest.raises(NFSeParseError):
        parse_documento(_xml("nacional_emitida.xml").replace(b'Id="NFS', b'Id="X'), CF)


# --- ingest -----------------------------------------------------------------

def _ingest(db, xmls, ultimo_nsu=None):
    from app.services.nfse_sync import ingest_payload

    return ingest_payload(db, cnpj_prestador=CF, periodo_inicio=date(2026, 5, 1),
                          periodo_fim=date(2026, 5, 31), origem="cron", disparado_por=None,
                          xmls=xmls, ultimo_nsu=ultimo_nsu)


def test_ingest_emitida_concilia_e_recebida_nao_gera_pagamento(db):  # noqa: F811
    job = _ingest(db, [_xml("nacional_emitida.xml"), _xml("nacional_recebida.xml")], ultimo_nsu=7)
    assert (job.total_nfs, job.auto_vinculadas, job.sem_match) == (2, 1, 0)

    rows = db.execute(text(
        "SELECT direcao, status_matching, contract_id, pagamento_id, chave_acesso "
        "FROM nfse_recebidas ORDER BY direcao")).fetchall()
    emitida, recebida = rows
    assert emitida[:3] == ("emitida", "auto", "c-1") and emitida[3] is not None
    assert emitida[4] == CHAVE_EMITIDA
    assert recebida[:4] == ("recebida", "recebida", None, None)
    assert db.execute(text("SELECT COUNT(*) FROM participacao_pagamentos")).scalar() == 1
    assert db.execute(text("SELECT ultimo_nsu FROM sync_jobs")).scalar() == 7


def test_ingest_dedupe_pela_chave_e_cancelamento_por_evento(db):  # noqa: F811
    _ingest(db, [_xml("nacional_emitida.xml")])
    job = _ingest(db, [_xml("nacional_emitida.xml"), _xml("nacional_evento_cancelamento.xml")])
    assert job.total_nfs == 1  # so o cancelamento; a nota repetida nao duplica
    assert db.execute(text("SELECT COUNT(*) FROM nfse_recebidas")).scalar() == 1
    row = db.execute(text("SELECT cancelada, status_matching FROM nfse_recebidas")).fetchone()
    assert (row[0], row[1]) == (1, "cancelada")


def test_numero_nacional_igual_a_numero_bhiss_nao_e_duplicata(db):  # noqa: F811
    # Nota antiga do BHISS com o mesmo numero da nova nacional, mesmo CNPJ.
    antiga = _xml("abrasf_minimo.xml").replace(b"12345678000199", CF.encode()).replace(
        b"<Numero>1000</Numero>", b"<Numero>12</Numero>")
    _ingest(db, [antiga])
    _ingest(db, [_xml("nacional_emitida.xml")])
    assert db.execute(text("SELECT COUNT(*) FROM nfse_recebidas")).scalar() == 2


def test_ultimo_nsu_endpoint_so_conta_jobs_ok(db, client, monkeypatch):  # noqa: F811
    from app.database import SessionLocal
    from app.routers import nfse_internal

    monkeypatch.setattr(nfse_internal.settings, "nfse_enabled", True)
    monkeypatch.setattr(nfse_internal.settings, "nfse_worker_token", "t")
    with SessionLocal() as s:
        _ingest(s, [], ultimo_nsu=40)
        s.execute(text("UPDATE sync_jobs SET status='erro_adn', ultimo_nsu=99 WHERE id=1"))
        _ingest(s, [], ultimo_nsu=30)
        s.commit()
    h = {"Authorization": "Bearer t"}
    assert client.get(f"/api/nfse/adn/ultimo-nsu?cnpj={CF}", headers=h).json() == {"ultimo_nsu": 30}
    assert client.get("/api/nfse/adn/ultimo-nsu?cnpj=11111111000111", headers=h).json() == {"ultimo_nsu": 0}


def test_ingest_endpoint_grava_ultimo_nsu(client, monkeypatch):
    from app.routers import nfse_internal

    monkeypatch.setattr(nfse_internal.settings, "nfse_enabled", True)
    monkeypatch.setattr(nfse_internal.settings, "nfse_worker_token", "t")
    r = client.post("/api/nfse/ingest", headers={"Authorization": "Bearer t"}, json={
        "cnpj_prestador": CF, "periodo_inicio": "2026-05-01", "periodo_fim": "2026-05-31",
        "xmls_b64": [base64.b64encode(_xml("nacional_recebida.xml")).decode()], "ultimo_nsu": 5,
    })
    assert r.status_code == 200 and r.json()["total_nfs"] == 1
    assert client.get(f"/api/nfse/adn/ultimo-nsu?cnpj={CF}",
                      headers={"Authorization": "Bearer t"}).json() == {"ultimo_nsu": 5}


# --- cliente ADN ------------------------------------------------------------

def _doc(nsu: int, xml: bytes = b"<x/>") -> dict:
    return {"NSU": nsu, "ChaveAcesso": "c", "TipoDocumento": "NFSE",
            "ArquivoXml": base64.b64encode(gzip.compress(xml)).decode()}


def _adn(respostas: dict[int, httpx.Response], pedidos: list | None = None) -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        nsu = int(req.url.path.rsplit("/", 1)[1])
        if pedidos is not None:
            pedidos.append(nsu)
        return respostas.get(nsu, httpx.Response(404))
    return httpx.Client(base_url="https://adn.teste/contribuintes", transport=httpx.MockTransport(handler))


def test_lotes_pagina_descarta_nsu_repetido_e_para_no_404():
    from workers.nfse_adn.client import lotes

    pedidos: list[int] = []
    adn = _adn({
        0: httpx.Response(200, json={"StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                                     "LoteDFe": [_doc(2, b"<b/>"), _doc(1, b"<a/>")]}),
        # camelCase e o NSU pedido de volta no lote
        2: httpx.Response(200, json={"statusProcessamento": "DOCUMENTOS_LOCALIZADOS",
                                     "loteDFe": [_doc(2), _doc(3, b"<c/>")]}),
    }, pedidos)
    assert list(lotes(adn, 0)) == [[(1, b"<a/>"), (2, b"<b/>")], [(3, b"<c/>")]]
    assert pedidos == [0, 2, 3]


@pytest.mark.parametrize("fim", [
    httpx.Response(404),
    httpx.Response(200, json={"StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO", "LoteDFe": []}),
    httpx.Response(400, json={"Erros": [{"Codigo": "E2215", "Descricao": "Nenhum documento localizado"}]}),
    httpx.Response(200, json={"StatusProcessamento": "DOCUMENTOS_LOCALIZADOS", "LoteDFe": [_doc(5)]}),
])
def test_lotes_condicoes_de_parada(fim):
    from itertools import islice

    from workers.nfse_adn.client import lotes

    # islice: sem a guarda de NSU o ultimo caso entra em loop; assim falha rapido.
    assert list(islice(lotes(_adn({5: fim}), 5), 3)) == []


def test_lotes_rejeicao_levanta():
    from workers.nfse_adn.client import ADNError, lotes

    adn = _adn({0: httpx.Response(400, json={"StatusProcessamento": "REJEICAO",
                                             "Erros": [{"Codigo": "E9999"}]})})
    with pytest.raises(ADNError, match="REJEICAO"):
        list(lotes(adn, 0))


def _honorario(chamadas: list, ultimo_nsu: int = 0) -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        chamadas.append(req)
        if req.url.path == "/api/nfse/adn/ultimo-nsu":
            return httpx.Response(200, json={"ultimo_nsu": ultimo_nsu})
        return httpx.Response(200, json={"total_nfs": 1})
    return httpx.Client(base_url="https://hon.teste", transport=httpx.MockTransport(handler))


def test_executar_ingere_um_post_por_lote_com_ultimo_nsu():
    import json

    from workers.nfse_adn.run import executar

    chamadas: list[httpx.Request] = []
    adn = _adn({10: httpx.Response(200, json={"LoteDFe": [_doc(11), _doc(12)]})})
    assert executar(CF, adn, _honorario(chamadas, ultimo_nsu=10)) == 0
    ingest = [json.loads(c.content) for c in chamadas if c.url.path == "/api/nfse/ingest"]
    assert len(ingest) == 1
    assert ingest[0]["ultimo_nsu"] == 12 and len(ingest[0]["xmls_b64"]) == 2


def test_executar_dry_run_nao_chama_o_honorario():
    from workers.nfse_adn.run import executar

    adn = _adn({0: httpx.Response(200, json={"LoteDFe": [_doc(1)]})})
    assert executar(CF, adn, None) == 0


def test_executar_erro_do_adn_reporta_erro_adn():
    from workers.nfse_adn.run import executar

    chamadas: list[httpx.Request] = []
    adn = _adn({0: httpx.Response(500, text="falha")})
    assert executar(CF, adn, _honorario(chamadas), nsu=0) == 3
    assert [c.url.params.get("status") for c in chamadas] == ["erro_adn"]


# --- certificado --------------------------------------------------------------

def _pfx(senha: bytes) -> bytes:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "teste")])
    agora = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(agora).not_valid_after(agora + timedelta(days=1))
            .sign(key, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(b"t", key, cert, None, BestAvailableEncryption(senha))


def test_certificado_carrega_e_apaga_o_diretorio_temporario(monkeypatch):
    import tempfile

    from workers.nfse_adn import cert

    criados: list[str] = []

    class Rastreado(tempfile.TemporaryDirectory):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            criados.append(self.name)

    monkeypatch.setattr(cert.tempfile, "TemporaryDirectory", Rastreado)
    ctx = cert.ssl_context_do_pfx(_pfx(b"segredo"), "segredo")
    assert ctx is not None
    assert len(criados) == 1 and not Path(criados[0]).exists()


def test_certificado_senha_errada_nao_vaza_a_senha():
    from workers.nfse_adn.cert import CertificadoError, ssl_context_do_pfx

    with pytest.raises(CertificadoError) as e:
        ssl_context_do_pfx(_pfx(b"segredo"), "errada")
    assert "errada" not in str(e.value) and "segredo" not in str(e.value)


# --- revisao da #111 --------------------------------------------------------

def test_nt007_valor_liquido_vem_de_vliq_e_csll_sem_pis_cofins():
    # NT 007: vRetCSLL = PIS + COFINS + CSLL retidos (65 + 300 + 100).
    from app.services.nfse_parser import parse_documento

    nf = parse_documento(_xml("nacional_emitida_nt007.xml"), CF)
    assert nf.valor_liquido == Decimal("8885.00")  # vLiq da nota; antes saia 8520
    assert (nf.pis, nf.cofins, nf.csll) == (Decimal("65.00"), Decimal("300.00"), Decimal("100.00"))


def test_falha_no_meio_do_ingest_finaliza_o_job_com_erro(db, monkeypatch):  # noqa: F811
    from app.services import nfse_sync

    def explode(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(nfse_sync, "match_nfse", explode)
    with pytest.raises(RuntimeError):
        _ingest(db, [_xml("nacional_emitida.xml")], ultimo_nsu=9)
    row = db.execute(text("SELECT status, motivo_falha, ultimo_nsu FROM sync_jobs")).fetchone()
    assert row[0] == "erro" and "boom" in row[1] and row[2] is None
    monkeypatch.undo()
    assert _ingest(db, [_xml("nacional_emitida.xml")]).status == "ok"  # sem 409 preso


def test_sql_do_nfse_nao_compara_boolean_com_inteiro():
    """No Postgres, boolean = 1 da erro ('operator does not exist'). O SQLite dos
    testes aceita, entao este teste olha o texto do SQL."""
    import re

    raiz = Path(__file__).parent.parent / "app"
    arquivos = [raiz / "services/nfse_sync.py", raiz / "services/nfse_pagamento.py",
                raiz / "routers/nfse.py", raiz / "routers/nfse_internal.py",
                raiz / "routers/admin_credenciais.py"]
    ruins = re.compile(r"\b(cancelada|ativo|vinculo_ativo|aprovada)\s*=\s*[01]\b|\bIS\s+:\w+")
    achados = [f"{a.name}: {m.group(0)}" for a in arquivos for m in ruins.finditer(a.read_text(encoding="utf-8"))]
    assert achados == []


def test_run_recusa_ingerir_fora_de_producao(monkeypatch):
    from workers.nfse_adn import run

    chamadas = []
    monkeypatch.setattr(run, "executar", lambda *a, **kw: chamadas.append(a) or 0)
    monkeypatch.setenv("NFSE_CERT_PFX_B64", base64.b64encode(_pfx(b"s")).decode())
    monkeypatch.setenv("NFSE_CERT_PFX_SENHA", "s")
    monkeypatch.setenv("HONORARIO_API_URL", "https://hon.teste")
    monkeypatch.setenv("NFSE_WORKER_TOKEN", "t")

    for base in ["", run.ADN_HOMOLOGACAO, "https://adn.nfse.gov.br.evil/contribuintes"]:
        monkeypatch.setenv("NFSE_ADN_BASE_URL", base)
        monkeypatch.setattr("sys.argv", ["run", "--cnpj", CF, "--ingerir"])
        with pytest.raises(SystemExit) as e:
            run.main()
        assert e.value.code == 2
    assert chamadas == []

    monkeypatch.setenv("NFSE_ADN_BASE_URL", run.ADN_PRODUCAO)
    with pytest.raises(SystemExit) as e:
        run.main()
    assert e.value.code == 0 and len(chamadas) == 1


@pytest.mark.skipif(not __import__("os").getenv("TEST_POSTGRES_URL"),
                    reason="defina TEST_POSTGRES_URL para rodar contra Postgres de verdade")
def test_ingest_completo_no_postgres():
    """Emitida (auto + pagamento), recebida e cancelamento num Postgres real."""
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base

    eng = create_engine(os.environ["TEST_POSTGRES_URL"])
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    try:
        with sessionmaker(bind=eng)() as s:
            s.execute(text("""
                INSERT INTO contracts (contract_id, status, client_name, client_email,
                                       current_version, cliente_docs, created_at, updated_at)
                VALUES ('c-1', 'ativo', 'X', 'x@x.com', 1, '["98765432000100"]', now(), now())"""))
            s.execute(text("""
                INSERT INTO participacoes (contract_id, beneficiario_email, beneficiario_nome,
                       tipo_honorario, percentual_captacao, percentual_performance, natureza,
                       cliente_cpf_cnpj, data_inicio, vinculo_ativo, aprovada, created_at, updated_at)
                VALUES ('c-1', 'b@x.com', 'B', 'mensalidade', 10, 0, 'contratual',
                        '98765432000100', '2024-08-01', TRUE, TRUE, now(), now())"""))
            s.commit()
            abrasf = _xml("abrasf_minimo.xml").replace(b"12345678000199", CF.encode())
            job = _ingest(s, [abrasf, _xml("nacional_emitida_nt007.xml"), _xml("nacional_recebida.xml"),
                              _xml("nacional_evento_cancelamento.xml")], ultimo_nsu=3)
            assert (job.status, job.erros, job.auto_vinculadas) == ("ok", 0, 2)
            _ingest(s, [abrasf])  # dedupe ABRASF (serie NULL) no Postgres
            rows = dict(s.execute(text(
                "SELECT COALESCE(chave_acesso, numero), status_matching FROM nfse_recebidas")).fetchall())
            assert rows == {"1000": "auto", CHAVE_EMITIDA: "cancelada",
                            "31062002112223330001440000000000000426100000000042": "recebida"}
            assert s.execute(text("SELECT valor_liquido FROM nfse_recebidas WHERE chave_acesso=:c"),
                             {"c": CHAVE_EMITIDA}).scalar() == Decimal("8885.00")
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()
