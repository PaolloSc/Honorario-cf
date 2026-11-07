"""Configuracao num lugar so': producao nao sobe sem o essencial; fora dela so' avisa."""
import pytest

from app.config import ESSENCIAIS_PRODUCAO, Settings

_COMPLETO = {
    "azure_tenant_id": "t", "azure_client_id": "c", "azure_client_secret": "s",
    "database_url": "postgresql://x", "docuseal_api_key": "k", "docuseal_webhook_secret": "w",
    "financeiro_email": "f@exemplo.test", "cf_signer_email": "a@exemplo.test",
    "testemunha1_nome": "Fulana", "testemunha1_email": "t@exemplo.test", "bank_account_info": "Banco X",
}


def _s(**kw):
    return Settings(_env_file=None, **{**_COMPLETO, **kw})


def test_producao_completa_sobe():
    _s(vercel_env="production").validate_critical()


@pytest.mark.parametrize("nome,campo", ESSENCIAIS_PRODUCAO)
def test_producao_sem_essencial_nao_sobe(nome, campo):
    with pytest.raises(RuntimeError, match=nome):
        _s(vercel_env="production", **{campo: ""}).validate_critical()


def test_fora_de_producao_so_avisa(caplog):
    _s(docuseal_webhook_secret="", bank_account_info="").validate_critical()
    assert "DOCUSEAL_WEBHOOK_SECRET" not in caplog.text  # so' cobrado em producao


def test_sem_dado_pessoal_como_padrao(monkeypatch):
    for nome, _ in ESSENCIAIS_PRODUCAO:
        monkeypatch.delenv(nome, raising=False)
    s = Settings(_env_file=None)
    for _, campo in ESSENCIAIS_PRODUCAO:
        assert getattr(s, campo) == "", campo
