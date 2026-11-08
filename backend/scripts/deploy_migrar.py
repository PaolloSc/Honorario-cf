"""Passo de build do deploy: leva o banco do ambiente ao esquema atual (`python scripts/deploy_migrar.py`).

Regras, para nunca derrubar um deploy por causa do passo e nunca mexer onde nao deve:
- so' roda quando VERCEL_ENV=production (o homolog tambem roda como production, no banco dele);
  preview e local ficam intactos;
- banco com tabelas e sem `alembic_version` (ainda nao carimbado): AVISA e segue, sem escrever nada;
- qualquer outro erro de migration falha o build: o deploy novo nao sobe e o antigo continua no ar.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def executar(ambiente: dict[str, str], migrar_fn) -> int:
    if ambiente.get("VERCEL_ENV") != "production":
        print(f"migrar: pulado (VERCEL_ENV={ambiente.get('VERCEL_ENV') or 'vazio'})")
        return 0
    from app.migrar import BancoSemCarimbo

    try:
        print(f"migrar: {migrar_fn()}")
    except BancoSemCarimbo as e:
        print(f"migrar: AVISO, nada foi feito. {e}")
    return 0


if __name__ == "__main__":
    from app.migrar import migrar

    sys.exit(executar(dict(os.environ), migrar))
