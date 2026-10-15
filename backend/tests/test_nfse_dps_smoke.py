"""Smoke test da DPS (producao restrita): XML, assinatura e envio. Sem rede.

O certificado e gerado aqui (autoassinado); nenhum .pfx ou senha real entra no repositorio."""
from __future__ import annotations

import base64
import datetime
import gzip
import json
import warnings
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID
from lxml import etree

from workers.nfse_adn.cert import CertificadoError, carregar_pfx, completar_cadeia
from workers.nfse_dps_smoke import run
from workers.nfse_dps_smoke.assinatura import DS, NS_DPS, assinar_dps
from workers.nfse_dps_smoke.dps import DpsParams, id_dps, montar_dps

XSD = Path(__file__).parent / "fixtures" / "nfse" / "xsd" / "DPS_v1.01.xsd"
CNPJ = "25463159000173"


def _nome(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _cert(chave, cn, emissor=None, chave_emissor=None, ca=False, aia=None):
    nome = _nome(cn)
    b = (x509.CertificateBuilder().subject_name(nome).issuer_name(emissor or nome)
         .public_key(chave.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(datetime.datetime(2025, 1, 1)).not_valid_after(datetime.datetime(2035, 1, 1))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if aia:
        b = b.add_extension(x509.AuthorityInformationAccess([x509.AccessDescription(
            AuthorityInformationAccessOID.CA_ISSUERS, x509.UniformResourceIdentifier(aia))]), critical=False)
    return b.sign(chave_emissor or chave, hashes.SHA256())


@pytest.fixture(scope="module")
def par():
    chave = rsa.generate_private_key(65537, 2048)
    return chave, _cert(chave, f"ESCRITORIO TESTE:{CNPJ}")


@pytest.fixture(scope="module")
def pfx(par):
    chave, cert = par
    return pkcs12.serialize_key_and_certificates(
        b"t", chave, cert, None, serialization.BestAvailableEncryption(b"senha-de-teste"))


def _params(**kw) -> DpsParams:
    base = dict(cnpj_prestador=CNPJ, n_dps=41, agora=datetime.datetime(
        2026, 10, 15, 10, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3))))
    return DpsParams(**{**base, **kw})


@pytest.fixture(scope="module")
def schema(tmp_path_factory):
    r"""XSD oficial v1.01. Unica correcao: o padrao de TSSerieDPS vem como '^0{0,4}\d{1,5}$', e em
    expressao regular de XSD '^' e '$' sao caracteres literais (o padrao ja e ancorado), entao o
    libxml2 recusaria qualquer serie. Tiramos so as ancoras, em copia."""
    d = tmp_path_factory.mktemp("xsd")
    for f in XSD.parent.glob("*.xsd"):
        (d / f.name).write_bytes(f.read_bytes().replace(rb'value="^0{0,4}\d{1,5}$"', rb'value="0{0,4}\d{1,5}"'))
    return etree.XMLSchema(etree.parse(str(d / "DPS_v1.01.xsd")))


# --- XML ----------------------------------------------------------------------

@pytest.mark.parametrize("kw", [
    {}, {"ibscbs": False}, {"op_simp_nac": "3"}, {"aliquota_iss": Decimal("2.00")}, {"valor": Decimal("1234.50")},
])
def test_dps_valida_no_xsd_oficial(schema, kw):
    schema.assertValid(etree.fromstring(montar_dps(_params(**kw))))


def test_id_dps_tem_45_posicoes_e_bate_com_o_exemplo_publicado():
    # Exemplo real de um desenvolvedor (forum ACBr): municipio 2304400, CNPJ, serie 900, nDPS 41.
    assert id_dps("2304400", "29416149000138", "900", 41) == "DPS230440022941614900013800900000000000000041"
    assert len(id_dps("3106200", CNPJ, "1", 1)) == 45


def test_dps_vai_para_producao_restrita_sem_prefixo_de_namespace():
    xml = montar_dps(_params())
    raiz = etree.fromstring(xml)
    assert raiz.findtext(f".//{{{NS_DPS}}}tpAmb") == "2"
    assert raiz.find(f"{{{NS_DPS}}}infDPS").get("Id") == id_dps("3106200", CNPJ, "900", 41)
    assert b"ns0:" not in xml and b"<DPS " in xml
    # dhEmi em Brasilia, sem fracao, 1 minuto no passado (competencia nao pode passar da emissao)
    assert raiz.findtext(f".//{{{NS_DPS}}}dhEmi") == "2026-10-15T09:59:00-03:00"


# --- assinatura ---------------------------------------------------------------

def _verifica(assinado: bytes, cert: x509.Certificate, perfil: str) -> None:
    """Verificador independente do assinador: segue os algoritmos DECLARADOS no XML (como o servidor),
    nao a tabela PERFIS, para pegar declarar um algoritmo e usar outro."""
    raiz = etree.fromstring(assinado)
    inf = raiz.find(f"{{{NS_DPS}}}infDPS")
    sig = raiz.find(f"{{{DS}}}Signature")
    ref = sig.find(f"{{{DS}}}SignedInfo/{{{DS}}}Reference")
    assert ref.get("URI") == "#" + inf.get("Id")
    c14n = sig.find(f"{{{DS}}}SignedInfo/{{{DS}}}CanonicalizationMethod").get("Algorithm")
    exclusive = c14n.endswith("xml-exc-c14n#")
    assert exclusive == (perfil == "sha256")
    hash_ = hashes.SHA256 if perfil == "sha256" else hashes.SHA1
    assert ref.find(f"{{{DS}}}DigestMethod").get("Algorithm").endswith("sha256" if perfil == "sha256" else "sha1")
    assert sig.find(f"{{{DS}}}SignedInfo/{{{DS}}}SignatureMethod").get("Algorithm").endswith(
        "rsa-sha256" if perfil == "sha256" else "rsa-sha1")
    h = hashes.Hash(hash_())
    h.update(etree.tostring(inf, method="c14n", exclusive=exclusive))
    assert base64.b64decode(ref.findtext(f"{{{DS}}}DigestValue")) == h.finalize()
    si = etree.tostring(sig.find(f"{{{DS}}}SignedInfo"), method="c14n", exclusive=exclusive)
    cert.public_key().verify(base64.b64decode(sig.findtext(f"{{{DS}}}SignatureValue")), si,
                             padding.PKCS1v15(), hash_())


@pytest.mark.parametrize("perfil", ["sha256", "sha1"])
def test_assinatura_confere_e_o_xml_assinado_continua_valido_no_xsd(schema, par, perfil):
    chave, cert = par
    assinado = assinar_dps(montar_dps(_params()), chave, cert, perfil)
    _verifica(assinado, cert, perfil)
    schema.assertValid(etree.fromstring(assinado))
    assert b"ds:" not in assinado  # E1228: sem prefixo de namespace
    # o certificado vai no KeyInfo
    x = etree.fromstring(assinado).findtext(f".//{{{DS}}}X509Certificate")
    assert base64.b64decode(x) == cert.public_bytes(serialization.Encoding.DER)


def test_alterar_a_dps_depois_de_assinar_quebra_a_verificacao(par):
    chave, cert = par
    assinado = assinar_dps(montar_dps(_params()), chave, cert).replace(b"<vServ>1.00<", b"<vServ>9.00<")
    with pytest.raises(AssertionError):
        _verifica(assinado, cert, "sha256")


def test_assinatura_confere_com_signxml(par):
    signxml = pytest.importorskip("signxml")
    chave, cert = par
    assinado = assinar_dps(montar_dps(_params()), chave, cert, "sha256")
    r = signxml.XMLVerifier().verify(assinado, x509_cert=cert.public_bytes(serialization.Encoding.PEM),
                                     id_attribute="Id")
    assert r.signed_xml.get("Id") == id_dps("3106200", CNPJ, "900", 41)


# --- trava: so producao restrita ----------------------------------------------

def test_host_e_fixo_em_producao_restrita():
    assert run.SEFIN_HOST == "https://sefin.producaorestrita.nfse.gov.br"
    assert all(b.startswith(run.SEFIN_HOST) for b in run.SEFIN_BASES)
    codigo = "".join(p.read_text(encoding="utf-8") for p in Path(run.__file__).parent.glob("*.py"))
    workflow = (Path(__file__).parents[2] / ".github/workflows/nfse-dps-smoke.yml").read_text(encoding="utf-8")
    for proibido in ("sefin.nfse.gov.br", "adn.nfse.gov.br"):
        assert proibido not in codigo and proibido not in workflow


# --- envio --------------------------------------------------------------------

def _http(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_enviar_manda_dps_em_gzip_base64_e_imprime_a_chave(capsys):
    visto = {}
    chave = "NFS" + "1" * 47

    def handler(req):
        visto["url"], visto["corpo"] = str(req.url), json.loads(req.content)
        return httpx.Response(201, json={"chaveAcesso": chave, "nfseXmlGZipB64": "xx"})

    assert run.enviar(_http(handler), b"<DPS/>") == 0
    assert visto["url"] == "https://sefin.producaorestrita.nfse.gov.br/SefinNacional/nfse"
    assert gzip.decompress(base64.b64decode(visto["corpo"]["dpsXmlGZipB64"])) == b"<DPS/>"
    out = capsys.readouterr().out
    assert "HTTP 201" in out and chave in out and "xx" not in out


def test_enviar_chave_vem_do_xml_da_nota_quando_nao_ha_campo(capsys):
    nfse = (f'<NFSe xmlns="{NS_DPS}"><infNFSe Id="NFS{"2" * 47}"/></NFSe>').encode()
    resp = {"nfseXmlGZipB64": base64.b64encode(gzip.compress(nfse)).decode()}
    assert run.enviar(_http(lambda req: httpx.Response(200, json=resp)), b"<DPS/>") == 0
    assert "2" * 47 in capsys.readouterr().out


def test_enviar_rejeicao_imprime_so_codigo_e_mensagem(capsys):
    corpo = {"erros": [{"Codigo": "E0010", "Descricao": "Serie fora da faixa"}, {"codigo": "E1228", "descricao": "prefixo"}]}
    assert run.enviar(_http(lambda req: httpx.Response(400, json=corpo)), b"<DPS/>") == 1
    out = capsys.readouterr().out
    assert "HTTP 400" in out and "rejeicao E0010: Serie fora da faixa" in out and "rejeicao E1228: prefixo" in out


def test_enviar_tenta_o_outro_prefixo_so_quando_a_rota_nao_existe(capsys):
    urls = []

    def handler(req):
        urls.append(str(req.url))
        if "/API/" in str(req.url):
            return httpx.Response(200, json={"chaveAcesso": "NFS" + "3" * 47})
        return httpx.Response(404, text="Not Found")

    assert run.enviar(_http(handler), b"<DPS/>") == 0
    assert urls == [f"{b}/nfse" for b in run.SEFIN_BASES]


def test_enviar_rejeicao_nao_tenta_o_outro_prefixo():
    urls = []

    def handler(req):
        urls.append(str(req.url))
        return httpx.Response(404, json={"erros": [{"Codigo": "E2404", "Descricao": "nao encontrada"}]})

    assert run.enviar(_http(handler), b"<DPS/>") == 1
    assert len(urls) == 1  # 404 com JSON de erro: a rota existe, nao e hora de reenviar


def test_enviar_pagina_html_do_servidor_sai_truncada(capsys):
    r = run.enviar(_http(lambda req: httpx.Response(403, text="<h2>403 - Forbidden</h2>" + "x" * 5000)), b"<DPS/>")
    assert r == 3
    assert len(capsys.readouterr().out) < 900


# --- main: a saida nao pode vazar segredo -------------------------------------

def test_main_dry_run_nao_imprime_senha_nem_pfx(monkeypatch, capsys, pfx):
    b64 = base64.b64encode(pfx).decode()
    monkeypatch.setenv("NFSE_CERT_PFX_B64", b64)
    monkeypatch.setenv("NFSE_CERT_PFX_SENHA", "senha-de-teste")
    assert run.main(["--cnpj", CNPJ, "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "assinada" in out and "titular com o CNPJ informado: sim" in out
    assert "senha-de-teste" not in out and b64[:40] not in out


def test_main_senha_errada_sai_com_2_sem_vazar(monkeypatch, capsys, pfx):
    monkeypatch.setenv("NFSE_CERT_PFX_B64", base64.b64encode(pfx).decode())
    monkeypatch.setenv("NFSE_CERT_PFX_SENHA", "errada-123")
    assert run.main(["--cnpj", CNPJ, "--dry-run"]) == 2
    assert "errada-123" not in capsys.readouterr().out


def test_main_sem_secrets_sai_com_2(monkeypatch):
    monkeypatch.delenv("NFSE_CERT_PFX_B64", raising=False)
    assert run.main(["--cnpj", CNPJ]) == 2


# --- pfx em BER e sem cadeia --------------------------------------------------

def test_pfx_em_ber_carrega(pfx):
    corpo = pfx[2:] if pfx[1] < 0x80 else pfx[2 + (pfx[1] & 0x7F):]
    ber = b"\x30\x80" + corpo + b"\x00\x00"  # SEQUENCE externa de tamanho indefinido
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # a cryptography avisa que le BER como fallback
        _, cert, extras = carregar_pfx(ber, "senha-de-teste")
    assert extras == [] and "ESCRITORIO TESTE" in cert.subject.rfc4514_string()


def test_pfx_senha_errada_nao_vaza():
    with pytest.raises(CertificadoError) as e:
        carregar_pfx(b"lixo", "senha-secreta")
    assert "senha-secreta" not in str(e.value)


def test_cadeia_ausente_no_pfx_e_completada_pelo_aia(monkeypatch):
    k_raiz, k_int, k_folha = (rsa.generate_private_key(65537, 2048) for _ in range(3))
    raiz = _cert(k_raiz, "AC RAIZ", ca=True)
    inter = _cert(k_int, "AC INTERMEDIARIA", raiz.subject, k_raiz, ca=True, aia="http://ac.teste/raiz.crt")
    folha = _cert(k_folha, "FOLHA", inter.subject, k_int, aia="http://ac.teste/inter.crt")
    servido = {"http://ac.teste/inter.crt": inter, "http://ac.teste/raiz.crt": raiz}
    baixados = []

    def falso_get(url, **kw):
        baixados.append(url)
        return httpx.Response(200, content=servido[url].public_bytes(serialization.Encoding.DER),
                              request=httpx.Request("GET", url))

    monkeypatch.setattr("workers.nfse_adn.cert.httpx.get", falso_get)
    assert completar_cadeia(folha, []) == [inter]  # a raiz autoassinada nao entra
    assert baixados == ["http://ac.teste/inter.crt", "http://ac.teste/raiz.crt"]
    baixados.clear()
    assert completar_cadeia(folha, [inter]) == [inter] and baixados == ["http://ac.teste/raiz.crt"]


def test_cadeia_sem_rede_devolve_o_que_tem(monkeypatch):
    k_i, k_f = rsa.generate_private_key(65537, 2048), rsa.generate_private_key(65537, 2048)
    inter = _cert(k_i, "AC", ca=True)
    folha = _cert(k_f, "FOLHA", inter.subject, k_i, aia="http://ac.teste/x.crt")

    def sem_rede(url, **kw):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr("workers.nfse_adn.cert.httpx.get", sem_rede)
    assert completar_cadeia(folha, []) == []


# --- IM, NBS, titular, saida do servidor --------------------------------------

def test_im_e_nbs_entram_no_lugar_do_leiaute_e_validam_no_xsd(schema):
    raiz = etree.fromstring(montar_dps(_params(im="123456", nbs="113012000")))
    schema.assertValid(raiz)
    inf = raiz.find(f"{{{NS_DPS}}}infDPS")
    assert [e.tag.split("}")[1] for e in inf.find(f"{{{NS_DPS}}}prest")] == ["CNPJ", "IM", "regTrib"]
    assert [e.tag.split("}")[1] for e in inf.find(f"{{{NS_DPS}}}serv/{{{NS_DPS}}}cServ")] == [
        "cTribNac", "xDescServ", "cNBS"]


def test_sem_im_e_nbs_nada_e_emitido():
    xml = montar_dps(_params())
    assert b"<IM>" not in xml and b"cNBS" not in xml


def test_main_nbs_com_pontos_e_normalizado_e_invalido_aborta(monkeypatch, capsys, pfx):
    monkeypatch.setenv("NFSE_CERT_PFX_B64", base64.b64encode(pfx).decode())
    monkeypatch.setenv("NFSE_CERT_PFX_SENHA", "senha-de-teste")
    assert run.main(["--cnpj", CNPJ, "--dry-run", "--nbs", "1.1301.20.00", "--im", "123"]) == 0
    assert run.main(["--cnpj", CNPJ, "--dry-run", "--nbs", "1.1301"]) == 2
    assert "9 digitos" in capsys.readouterr().out


def test_titular_que_nao_confere_aborta_antes_de_enviar(monkeypatch, capsys, pfx):
    monkeypatch.setenv("NFSE_CERT_PFX_B64", base64.b64encode(pfx).decode())
    monkeypatch.setenv("NFSE_CERT_PFX_SENHA", "senha-de-teste")
    monkeypatch.setattr(run, "enviar", lambda *a: pytest.fail("enviou com certificado de outro CNPJ"))
    monkeypatch.setattr(run, "ssl_context_do_pfx", lambda *a: pytest.fail("abriu TLS"))
    assert run.main(["--cnpj", "11222333000181"]) == 2
    out = capsys.readouterr().out
    assert "NAO CONFERE" in out and "abortado" in out


def test_saida_do_servidor_nao_vira_comando_do_actions(capsys):
    corpo = {"erros": [{"Codigo": "E1", "Descricao": "ok\n::add-mask::segredo\n::error::x"}]}
    run.enviar(_http(lambda req: httpx.Response(400, json=corpo)), b"<DPS/>")
    run.enviar(_http(lambda req: httpx.Response(500, text="a\n::set-output name=x::y")), b"<DPS/>")
    linhas = capsys.readouterr().out.splitlines()
    assert len(linhas) == 6  # 2 envios x (POST, HTTP, rejeicao ou texto): o texto do servidor ficou em 1 linha
    assert not any(l.lstrip().startswith("::") for l in linhas)
    assert not any("::" in l for l in linhas)


def test_workflow_so_le_o_conteudo_do_repositorio():
    wf = (Path(__file__).parents[2] / ".github/workflows/nfse-dps-smoke.yml").read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in wf
    assert "--im" in wf and "--nbs" in wf
