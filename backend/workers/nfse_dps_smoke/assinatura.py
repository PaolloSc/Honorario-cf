"""XMLDSig enveloped da DPS (assina o infDPS, Reference "#<Id>").

Dois perfis, porque a documentacao oficial nao fixa um e os relatos divergem:
- sha256 (padrao): exc-c14n, rsa-sha256, digest sha256 (como as bibliotecas que
  ja passaram na producao restrita);
- sha1: c14n inclusivo, rsa-sha1, digest sha1 (padrao herdado da NF-e).
A assinatura sai sem prefixo ('ds:'): o SEFIN rejeita prefixo de namespace (E1228)."""
from __future__ import annotations

import base64

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import Encoding
from lxml import etree

DS = "http://www.w3.org/2000/09/xmldsig#"
NS_DPS = "http://www.sped.fazenda.gov.br/nfse"

PERFIS = {
    "sha256": dict(
        c14n="http://www.w3.org/2001/10/xml-exc-c14n#", exclusive=True,
        assinatura="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
        digest="http://www.w3.org/2001/04/xmlenc#sha256", hash=hashes.SHA256,
    ),
    "sha1": dict(
        c14n="http://www.w3.org/TR/2001/REC-xml-c14n-20010315", exclusive=False,
        assinatura="http://www.w3.org/2000/09/xmldsig#rsa-sha1",
        digest="http://www.w3.org/2000/09/xmldsig#sha1", hash=hashes.SHA1,
    ),
}
ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"


def _c14n(el, perfil) -> bytes:
    return etree.tostring(el, method="c14n", exclusive=perfil["exclusive"], with_comments=False)


def _ds(pai, nome, **attrs):
    return etree.SubElement(pai, f"{{{DS}}}{nome}", **attrs)


def assinar_dps(dps_xml: bytes, key, cert: x509.Certificate, perfil: str = "sha256") -> bytes:
    p = PERFIS[perfil]
    raiz = etree.fromstring(dps_xml)
    inf = raiz.find(f"{{{NS_DPS}}}infDPS")
    id_ = inf.get("Id")

    sig = etree.SubElement(raiz, f"{{{DS}}}Signature", nsmap={None: DS})
    si = _ds(sig, "SignedInfo")
    _ds(si, "CanonicalizationMethod", Algorithm=p["c14n"])
    _ds(si, "SignatureMethod", Algorithm=p["assinatura"])
    ref = _ds(si, "Reference", URI=f"#{id_}")
    tr = _ds(ref, "Transforms")
    _ds(tr, "Transform", Algorithm=ENVELOPED)
    _ds(tr, "Transform", Algorithm=p["c14n"])
    _ds(ref, "DigestMethod", Algorithm=p["digest"])
    h = hashes.Hash(p["hash"]())
    h.update(_c14n(inf, p))
    _ds(ref, "DigestValue").text = base64.b64encode(h.finalize()).decode()

    valor = _ds(sig, "SignatureValue")
    # A Signature ja esta na arvore: o SignedInfo e canonicalizado no mesmo contexto do verificador.
    valor.text = base64.b64encode(key.sign(_c14n(si, p), padding.PKCS1v15(), p["hash"]())).decode()
    x509_data = _ds(_ds(sig, "KeyInfo"), "X509Data")
    _ds(x509_data, "X509Certificate").text = base64.b64encode(cert.public_bytes(Encoding.DER)).decode()

    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8")
