from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.services.nfse_matcher import MatchStatus, match_nfse


@dataclass
class FakeContract:
    contract_id: str
    cliente_docs: list[str]
    data_inicio: date
    data_fim: date | None = None


def _nf(tomador_doc="98765432000100", competencia=date(2026, 5, 1), discriminacao=None):
    from app.models.nfse import NFSeData

    return NFSeData(
        cnpj_prestador="12345678000199",
        numero="1",
        competencia=competencia,
        data_emissao=competencia,
        tomador_doc=tomador_doc,
        valor_servicos=Decimal("1000"),
        discriminacao=discriminacao,
        xml_raw=b"x",
    )


def test_um_contrato_match_auto():
    cs = [FakeContract("abc12345", ["98765432000100"], date(2025, 1, 1))]
    r = match_nfse(_nf(), cs)
    assert r.status == MatchStatus.AUTO
    assert r.contract_id == "abc12345"


def test_zero_contratos_sem_match():
    r = match_nfse(_nf(), [])
    assert r.status == MatchStatus.SEM_MATCH


def test_contrato_encerrado_antes_da_competencia_ignora():
    cs = [FakeContract("abc12345", ["98765432000100"], date(2024, 1, 1), data_fim=date(2026, 4, 30))]
    r = match_nfse(_nf(), cs)
    assert r.status == MatchStatus.SEM_MATCH


def test_dois_contratos_sem_id_discriminacao_pendente():
    cs = [
        FakeContract("aaaaaaaa", ["98765432000100"], date(2025, 1, 1)),
        FakeContract("bbbbbbbb", ["98765432000100"], date(2025, 6, 1)),
    ]
    r = match_nfse(_nf(discriminacao="Servicos maio"), cs)
    assert r.status == MatchStatus.PENDENTE
    assert set(r.candidatos) == {"aaaaaaaa", "bbbbbbbb"}


def test_dois_contratos_com_id_discriminacao_resolve():
    cs = [
        FakeContract("aaaaaaaa", ["98765432000100"], date(2025, 1, 1)),
        FakeContract("bbbbbbbb", ["98765432000100"], date(2025, 6, 1)),
    ]
    r = match_nfse(_nf(discriminacao="Ref #bbbbbbbb maio"), cs)
    assert r.status == MatchStatus.AUTO
    assert r.contract_id == "bbbbbbbb"


def test_pf_tomador_casa_por_cpf():
    cs = [FakeContract("xyz12345", ["12345678901"], date(2025, 1, 1))]
    r = match_nfse(_nf(tomador_doc="12345678901"), cs)
    assert r.status == MatchStatus.AUTO


def test_normaliza_discriminacao_case_insensitive():
    cs = [
        FakeContract("aaaaaaaa", ["98765432000100"], date(2025, 1, 1)),
        FakeContract("bbbbbbbb", ["98765432000100"], date(2025, 1, 1)),
    ]
    r = match_nfse(_nf(discriminacao="REF #BBBBBBBB"), cs)
    assert r.status == MatchStatus.AUTO
    assert r.contract_id == "bbbbbbbb"
