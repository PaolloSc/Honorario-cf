"""Link de assinatura pelo WhatsApp: o numero vai ao DocuSeal e volta com o link."""
from app.services.docuseal import _submitter, telefone_e164


def test_celular_brasileiro_vira_formato_internacional():
    assert telefone_e164("(31) 99999-1234") == "+5531999991234"
    assert telefone_e164("31 3333-1234") == "+553133331234"
    assert telefone_e164("+55 31 99999-1234") == "+5531999991234"


def test_numero_vazio_ou_invalido_nao_vai():
    assert telefone_e164("") is None
    assert telefone_e164(None) is None
    assert telefone_e164("1234") is None


def test_submitter_leva_o_whatsapp_so_quando_existe():
    com = _submitter({"email": "c@x.com", "name": "Cliente", "role": "Contratante", "phone": "(31) 99999-1234"}, True)
    sem = _submitter({"email": "c@x.com", "name": "Cliente", "role": "Contratante"}, True)
    assert com["phone"] == "+5531999991234"
    assert "phone" not in sem


def test_link_de_assinatura_vem_do_slug():
    """A consulta da submissao nao traz embed_src, so' o slug: o link e' montado do endereco do DocuSeal."""
    from app.services.docuseal import link_assinatura

    assert link_assinatura("https://api.docuseal.com", "abc123") == "https://docuseal.com/s/abc123"
    assert link_assinatura("https://api.docuseal.eu/", "abc123") == "https://docuseal.eu/s/abc123"
    assert link_assinatura("https://assinar.cf.com.br/api", "abc123") == "https://assinar.cf.com.br/s/abc123"
    assert link_assinatura("https://api.docuseal.com", "") == ""
