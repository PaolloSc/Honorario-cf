"""Cria usuários de teste no banco local.

Uso:
    cd backend
    python seed_test_users.py

Requer DEV_MODE=true no .env. Não usar em produção.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, UserDB, init_db

USUARIOS_TESTE = [
    {
        "azure_id": "dev::admin@teste.local",
        "email": "admin@teste.local",
        "name": "Admin Teste",
        "role": "admin",
    },
    {
        "azure_id": "dev::financeiro@teste.local",
        "email": "financeiro@teste.local",
        "name": "Financeiro Teste",
        "role": "financeiro",
    },
    {
        "azure_id": "dev::advogado@teste.local",
        "email": "advogado@teste.local",
        "name": "Advogado Teste",
        "role": "advogado",
    },
]


def main():
    init_db()
    db = SessionLocal()
    try:
        for u in USUARIOS_TESTE:
            existing = db.query(UserDB).filter(UserDB.azure_id == u["azure_id"]).first()
            if existing:
                existing.role = u["role"]
                existing.name = u["name"]
                print(f"[atualizado] {u['email']} ({u['role']})")
            else:
                db.add(
                    UserDB(
                        azure_id=u["azure_id"],
                        email=u["email"],
                        name=u["name"],
                        role=u["role"],
                        created_at=datetime.now(timezone.utc),
                    )
                )
                print(f"[criado]     {u['email']} ({u['role']})")
        db.commit()
        print("\nUsuarios prontos. Habilite DEV_MODE=true no .env do backend.")
        print("Login via header HTTP:")
        print("  X-Dev-User-Email: financeiro@teste.local")
        print("  X-Dev-User-Role:  financeiro")
    finally:
        db.close()


if __name__ == "__main__":
    main()
