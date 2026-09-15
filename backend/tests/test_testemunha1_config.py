"""A Testemunha 1 fixa precisa ter o mesmo nome no roster e na config.

O nome da config e' o que vai para o DocuSeal e para a linha de assinatura do
contrato. Ele ficou "Lilian Siqueira" enquanto o roster de colaboradores dizia
"Lilian Silveira Correa" — contratos sairam assinados com o nome errado, e nada
acusou porque os dois lugares nunca se olhavam.
"""

import importlib.util
from pathlib import Path

from app.config import settings

_SEED = Path(__file__).resolve().parent.parent / "seed_colaboradores.py"


def _colaboradores() -> list[tuple[str, str, str | None]]:
    spec = importlib.util.spec_from_file_location("seed_colaboradores", _SEED)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.COLABORADORES


def test_testemunha1_tem_o_mesmo_nome_do_roster():
    por_email = {
        (email or "").lower(): nome for nome, _papel, email in _colaboradores()
    }
    nome_no_roster = por_email.get(settings.testemunha1_email.lower())

    assert nome_no_roster, (
        f"{settings.testemunha1_email} nao esta no roster de colaboradores — "
        "a Testemunha 1 fixa precisa estar cadastrada."
    )
    assert settings.testemunha1_nome == nome_no_roster, (
        f"Nome divergente para {settings.testemunha1_email}: "
        f"config={settings.testemunha1_nome!r} roster={nome_no_roster!r}. "
        "O nome da config e' o que assina o contrato."
    )


def test_env_example_documenta_o_mesmo_nome():
    """O .env.example e' o que alguem copia ao montar um ambiente novo."""
    env = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")
    assert f"TESTEMUNHA1_NOME={settings.testemunha1_nome}" in env
