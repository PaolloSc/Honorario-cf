"""Popula o cadastro de testemunhas com os colaboradores do escritório.

O escritório também usa gente da casa (sócios, advogados, financeiro...) como
testemunha em contratos, não só os parceiros externos. Este script lê a
tabela ``colaboradores`` (fonte: seed_colaboradores.py) e replica cada
colaborador ativo com e-mail em ``testemunhas`` — ao contrário do seed de
parceiros, a lista não é fixa aqui: acompanha o roster de colaboradores
automaticamente.

Uso:
    cd backend
    python seed_testemunhas_colaboradores.py

Idempotente: faz upsert por ``email`` (não duplica em reexecuções).
Funciona em SQLite local (honorarios.db) ou PostgreSQL via DATABASE_URL.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import ColaboradorDB, TestemunhaDB, SessionLocal, init_db


def main():
    init_db()
    db = SessionLocal()
    criados = atualizados = 0
    try:
        colaboradores = (
            db.query(ColaboradorDB)
            .filter(ColaboradorDB.ativo.is_(True), ColaboradorDB.email.isnot(None))
            .order_by(ColaboradorDB.nome)
            .all()
        )
        sem_email = (
            db.query(ColaboradorDB)
            .filter(ColaboradorDB.ativo.is_(True), ColaboradorDB.email.is_(None))
            .order_by(ColaboradorDB.nome)
            .all()
        )

        for c in colaboradores:
            existing = db.query(TestemunhaDB).filter(TestemunhaDB.email == c.email).first()
            if existing:
                existing.nome = c.nome
                existing.ativo = True
                atualizados += 1
                print(f"[atualizado] {c.nome} <{c.email}>")
            else:
                db.add(
                    TestemunhaDB(
                        nome=c.nome,
                        email=c.email,
                        ativo=True,
                        created_by="seed",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                criados += 1
                print(f"[criado]     {c.nome} <{c.email}>")

        db.commit()

        print(f"\nOK. Criados={criados} Atualizados={atualizados}")
        if sem_email:
            print(f"\nSem e-mail no cadastro, não replicados ({len(sem_email)}):")
            for c in sem_email:
                print(f"  - {c.nome}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
