"""Participacao: campos de base (escopo/honorario)."""
from app.models.contract import Participacao


def test_base_fields_aceitos():
    p = Participacao(
        tem_participacao=True,
        base_tipo="honorario",
        base_escopo_index=0,
        base_honorario="mensalidade",
        base_label="Consultoria LGPD · Mensalidade",
    )
    assert p.base_tipo == "honorario"
    assert p.base_escopo_index == 0
    assert p.base_honorario == "mensalidade"
    assert p.base_label == "Consultoria LGPD · Mensalidade"


def test_base_fields_opcionais_legado():
    p = Participacao(tem_participacao=True)
    assert p.base_tipo is None
    assert p.base_escopo_index is None
    assert p.base_label is None


def test_email_request_aceita_base():
    from app.routers.email import ParticipacaoEmailRequest
    r = ParticipacaoEmailRequest(
        contract_id="x", cliente_nome="Fulano",
        base_tipo="escopo", base_label="Consultoria LGPD",
    )
    assert r.base_tipo == "escopo"
    assert r.base_label == "Consultoria LGPD"
