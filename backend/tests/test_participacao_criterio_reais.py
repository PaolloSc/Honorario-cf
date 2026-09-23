"""Critério geral em R$ + advogado com % próprio: o que chega ao financeiro."""
import pytest

from app.auth import CurrentUser, get_current_user
from app.database import ParticipacaoDB, SessionLocal
from app.main import app
from app.utils.participacao import linhas_participacao

from tests.test_contract_generator_fidelidade import _base_req

PARTICIPACAO = {
    "tem_participacao": True,
    "valor_tipo": "valor",
    "valor_monetario": 5000,
    "responsavel_gestao": "Mônica",
    "participantes": [{"nome": "Mônica", "natureza": "Captação", "percentual": "10"}],
}


def test_criterio_geral_em_reais_e_percentual_da_monica_saem_na_ficha():
    """Hoje: R$ 5.000 geral sai formatado e a Mônica sai com os 10% dela."""
    linhas = dict(linhas_participacao(PARTICIPACAO))
    assert linhas["Valor"] == "R$ 5.000,00"
    assert linhas["Para quem — Mônica"].startswith("Captação, 10%")


def test_valor_proprio_da_monica_avisa_que_substitui_o_geral():
    """Os 10% da Mônica substituem os R$ 5.000; a ficha precisa dizer, senão lê-se 10% de R$ 5.000."""
    linhas = dict(linhas_participacao(PARTICIPACAO))
    assert "geral" in linhas["Para quem — Mônica"]


@pytest.fixture
def _override_auth():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="gabriela@test.com", name="Gabriela", role="advogado")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_rascunho_do_financeiro_formata_reais_igual_a_ficha(client, _override_auth):
    """O rascunho do financeiro escrevia 'R$ 5000.00' enquanto a ficha diz 'R$ 5.000,00'."""
    req = _base_req()
    req["participacao"] = PARTICIPACAO
    assert client.post("/api/contract/generate", json=req).status_code == 200
    with SessionLocal() as db:
        rascunho = db.query(ParticipacaoDB).one()
    assert "R$ 5.000,00" in rascunho.observacoes
