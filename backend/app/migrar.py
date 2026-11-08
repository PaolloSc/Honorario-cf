"""Leva o banco ao esquema atual: `python -m app.migrar`.

Tres casos, decididos pelo que o banco ja' tem:
- com `alembic_version`: aplica as migrations pendentes (`upgrade head`);
- vazio (nenhuma tabela): cria o esquema pelos modelos e carimba como `head`
  (as migrations 0001-0017 partem de tabelas que o create_all criou, entao nao rodam do zero);
- com tabelas mas sem `alembic_version` (producao hoje): RECUSA. Esse banco precisa antes do
  carimbo conferido (`python scripts/comparar_esquema.py`, depois `alembic stamp 0017`).
"""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import Base, engine
from app.models import emissao_db, nfse_db  # noqa: F401  (registram suas tabelas em Base.metadata)

BACKEND_DIR = Path(__file__).resolve().parent.parent


class BancoSemCarimbo(Exception):
    pass


def _config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def migrar() -> str:
    """Devolve o que fez: 'upgrade', 'baseline'."""
    tabelas = set(inspect(engine).get_table_names())
    if "alembic_version" in tabelas:
        command.upgrade(_config(), "head")
        return "upgrade"
    if tabelas:
        raise BancoSemCarimbo(
            "O banco tem tabelas mas nao tem alembic_version. Confira o esquema com "
            "scripts/comparar_esquema.py e carimbe com `alembic stamp 0017` antes de migrar."
        )
    Base.metadata.create_all(bind=engine)
    command.stamp(_config(), "head")
    return "baseline"


if __name__ == "__main__":
    try:
        print(migrar())
    except BancoSemCarimbo as e:
        print(e, file=sys.stderr)
        sys.exit(2)
