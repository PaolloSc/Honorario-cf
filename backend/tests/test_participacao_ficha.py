"""ParticipacaoEmailRequest: novos campos + migracao."""
from app.routers.email import ParticipacaoEmailRequest


def test_request_aceita_campos_novos():
    r = ParticipacaoEmailRequest(
        contract_id="c1",
        cliente_nome="Cliente",
        valor_tipo="valor",
        valor_monetario=5000.0,
        para_quem=["Bruno", "Ana"],
        contato_financeiro_nome="Carlos",
        contato_financeiro_email="c@x.com",
        contato_financeiro_telefone="(31) 99999-0000",
    )
    assert r.valor_tipo == "valor"
    assert r.valor_monetario == 5000.0
    assert r.para_quem == ["Bruno", "Ana"]
    assert r.contato_financeiro_email == "c@x.com"


def test_request_migra_para_quem_string():
    r = ParticipacaoEmailRequest(contract_id="c1", cliente_nome="X", para_quem="Bruno")
    assert r.para_quem == ["Bruno"]
