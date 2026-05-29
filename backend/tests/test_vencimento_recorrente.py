"""Vencimento recorrente com data de calendário deve render 'todo dia DD'."""
from app.services.contract_generator import ContractGenerator


def test_recorrente_com_data_usa_todo_dia():
    g = ContractGenerator()
    assert g._vencimento_combined("2026-01-05", None, None, recorrente=True) == "todo dia 05"


def test_nao_recorrente_com_data_mantem_em_data():
    g = ContractGenerator()
    assert g._vencimento_combined("2026-01-05", None, None, recorrente=False) == "em 05/01/2026"


def test_recorrente_com_data_e_obs_concatena():
    g = ContractGenerator()
    assert (
        g._vencimento_combined("2026-01-05", "ajustável", None, recorrente=True)
        == "todo dia 05 (ajustável)"
    )


def test_recorrente_sem_data_sem_obs_cai_no_legacy():
    # Legacy path (sem data de calendário) deve retornar exatamente esta string.
    g = ContractGenerator()
    assert g._vencimento_combined(None, None, "5", recorrente=True) == "no dia 5 de cada mês"
