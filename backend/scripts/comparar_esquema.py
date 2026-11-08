"""Compara o esquema de um banco com os modelos. SO' LEITURA: nao cria, altera nem carimba nada.

Uso: DATABASE_URL=... python scripts/comparar_esquema.py
Saida: uma linha por diferenca (tabela/coluna faltando ou sobrando, tipo, nulabilidade). Codigo 0 se
nao ha diferenca, 1 se ha. Serve para decidir se o banco pode receber `alembic stamp 0017`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.models import emissao_db, nfse_db  # noqa: E402,F401  (registram suas tabelas em Base.metadata)


def diferencas(conn) -> list[str]:
    ctx = MigrationContext.configure(conn, opts={"compare_type": True, "compare_server_default": False})
    saida: list[str] = []

    def achatar(itens):
        for d in itens:
            if isinstance(d, list):
                achatar(d)
            else:
                saida.append(_descrever(d))

    achatar(compare_metadata(ctx, Base.metadata))
    return sorted(saida)


def _descrever(d) -> str:
    acao = d[0]
    if acao in ("add_table", "remove_table"):
        return f"{acao}: {d[1].name}"
    if acao in ("add_column", "remove_column"):
        return f"{acao}: {d[2]}.{d[3].name}"
    if acao.startswith("modify_"):
        return f"{acao}: {d[2]}.{d[3]} ({d[5]} -> {d[6]})"
    return f"{acao}: {d[1:]}"


if __name__ == "__main__":
    with engine.connect() as conn:  # conexao de leitura; nada e' confirmado
        itens = diferencas(conn)
    for i in itens:
        print(i)
    print(f"{len(itens)} diferenca(s)", file=sys.stderr)
    sys.exit(1 if itens else 0)
