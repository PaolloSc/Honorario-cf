"""Popula o roster de colaboradores do escritório (advogados/sócios/etc.).

Uso:
    cd backend
    python seed_colaboradores.py

Idempotente: faz upsert por ``nome`` (não duplica em reexecuções).
Funciona em SQLite local (honorarios.db) ou PostgreSQL via DATABASE_URL.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import ColaboradorDB, SessionLocal, init_db

# ordem: socio=1, advogado=2, estagiario=3, demais=4 (ordenação secundária por nome)
_ORDEM = {"socio": 1, "advogado": 2, "estagiario": 3}

# (nome, papel, email)  — email None quando não fornecido
COLABORADORES = [
    ("André Fortes Chaves", "advogado", "andre@carvalhofurtadoadv.com.br"),
    ("Caio César Amaral Franco", "socio", "caio@carvalhofurtadoadv.com.br"),
    ("Clara Marques de Albuquerque", "advogado", "clara.albuquerque@carvalhofurtadoadv.com.br"),
    ("Cristina Mascarenhas Diniz de Magalhães Santos", "advogado", "cristina.mascarenhas@carvalhofurtadoadv.com.br"),
    ("Gabriel Siqueira Eliazar de Carvalho", "socio", "gabriel@carvalhofurtadoadv.com.br"),
    ("Gabriela Peixoto Mello de Azevedo", "advogado", "gabriela.azevedo@carvalhofurtadoadv.com.br"),
    ("Marcello Silva Nunes Leite", "advogado", "marcello.leite@carvalhofurtadoadv.com.br"),
    ("Marcelo Pinheiro Chagas", "socio", "marcelo@carvalhofurtadoadv.com.br"),
    ("Marco Tulio Fonseca Furtado", "socio", "marcotulio@carvalhofurtadoadv.com.br"),
    ("Mariana Krollmann Fogli", "socio", "mariana@carvalhofurtadoadv.com.br"),
    ("Mônica Furtado Pinheiro Chagas", "socio", "monica@carvalhofurtadoadv.com.br"),
    ("Natália Xavier Cunha", "socio", "natalia@carvalhofurtadoadv.com.br"),
    ("Sérgio Adolfo Eliazar de Carvalho", "socio", "sergio.carvalho@carvalhofurtadoadv.com.br"),
    ("Isabela Vicentino Silva", "estagiario", "isabela.vicentino@carvalhofurtadoadv.com.br"),
    ("Lilian Silveira Correa", "financeiro", "financeiro@carvalhofurtadoadv.com.br"),
    ("Marcela Leite Kato", "estagiario", "trabalhista3@carvalhofurtadoadv.com.br"),
    ("Maria Karolyne Moraes Malard", "recepcionista", "arquivo@carvalhofurtadoadv.com.br"),
    ("Thaíza Alice Pereira da Silva", "estagiario", "thaiza.silva@carvalhofurtadoadv.com.br"),
    ("Victor Barbosa Horta", "estagiario", "victor.horta@carvalhofurtadoadv.com.br"),
    ("Paollo Sanchez", "dev", "paollo.sanchez@carvalhofurtadoadv.com.br"),
]


def main():
    init_db()
    db = SessionLocal()
    criados = atualizados = 0
    try:
        for nome, papel, email in COLABORADORES:
            ordem = _ORDEM.get(papel, 4)
            existing = db.query(ColaboradorDB).filter(ColaboradorDB.nome == nome).first()
            if existing:
                existing.papel = papel
                existing.email = email
                existing.ordem = ordem
                existing.ativo = True
                atualizados += 1
                print(f"[atualizado] {nome} ({papel})")
            else:
                db.add(
                    ColaboradorDB(
                        nome=nome,
                        email=email,
                        papel=papel,
                        ativo=True,
                        ordem=ordem,
                        created_by="seed",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                criados += 1
                print(f"[criado]     {nome} ({papel})")
        # Reconciliação: desativa quem está no banco mas saiu do roster.
        nomes_roster = {nome for nome, _, _ in COLABORADORES}
        desativados = 0
        for c in db.query(ColaboradorDB).filter(ColaboradorDB.ativo.is_(True)).all():
            if c.nome not in nomes_roster:
                c.ativo = False
                desativados += 1
                print(f"[desativado] {c.nome} (fora do roster)")

        db.commit()

        if desativados:
            print(f"Desativados (fora do roster): {desativados}")

        total = db.query(ColaboradorDB).count()
        participaveis = (
            db.query(ColaboradorDB)
            .filter(ColaboradorDB.papel.in_(("socio", "advogado")))
            .count()
        )
        print(
            f"\nOK. Criados={criados} Atualizados={atualizados} "
            f"Total={total} Participaveis(advogado/socio)={participaveis}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
