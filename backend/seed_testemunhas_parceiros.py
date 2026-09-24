"""Popula o cadastro de testemunhas com os parceiros do escritório.

Fonte: exportação de contatos (grupo "Parceiro", sem a classificação
"Fornecedor"). Contatos sem e-mail cadastrado na exportação ficam de fora —
e-mail é obrigatório para testemunha (usado pelo DocuSeal).

Uso:
    cd backend
    python seed_testemunhas_parceiros.py

Idempotente: faz upsert por ``email`` (não duplica em reexecuções).
Funciona em SQLite local (honorarios.db) ou PostgreSQL via DATABASE_URL.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import TestemunhaDB, SessionLocal, init_db

# (nome, email) — parceiros (grupo "Parceiro", sem "Fornecedor") com e-mail
# cadastrado na exportação de contatos.
PARCEIROS = [
    ("AccounTech Contabilidade e Tecnologia Ltda.", "contato@accountechcontabilidade.com.br"),
    ("Ana Clara Vogler", "anaclara@voglerlawoffices.com"),
    ("Antoine Reymondon", "antoine.reymondon@europartner.com.br"),
    ("Bernardo Lucena", "bernardo.lucena@insigneo.com"),
    ("Carlos Alberto Teixeira de Oliveira", "cato@mercadocomum.com"),
    ("David Emmerich", "DEmmerich@hp-legal.com"),
    ("Drielle Bennett", "drielle@heislerrosenfeldlaw.com"),
    ("Ester Xavier Cunha de Oliveira", "ester@decisaocontabilidade.com.br"),
    ("Flávia Santos Lloyd", "flloyd@santoslloydlaw.com"),
    ("Francisco Américo França", "francisco.franca@ffvp.com.br"),
    ("Freitas Macedo Advogados Associados", "catiane.damacena@freitasmacedo.com"),
    ("João Gomes Mtx, CPA", "joaogomes@drummondadvisors.com"),
    ("Juliana Maroja", "jumarojarr@gmail.com"),
    ("Leonardo Tavares", "leonardo@michilestavares.com"),
    ("Mandaliti Advogados", "contato@mandaliti.com.br"),
    ("Marcus Vinícius de Carvalho Rezende Reis", "marcus@reisadvogados.com"),
    ("Mauro Cavanha Conceição", "mauro@cavanhalawfirm.com"),
    ("MMCZ - Menezes, Magalhães, Coelho e Zarif Sociedade de Advogados", "mmcz@mmcz.adv.br"),
    ("Pedro de Morais Dalosto", "pedro@docadvogados.com"),
    ("Rodrigo Siracusa", "rsiracusa@drummondadvisors.com"),
    ("Souza Machado, Gonçalves e Arruda, Weyll e Midon Advocacia", "contato@smga.com.br"),
    ("Telder Andrade Lage", "telder.lage@plbradvogados.com.br"),
    ("Welke Borges", "wellke.borges@reisadvogados.com"),
]

# Parceiros sem e-mail na exportação — não dá pra cadastrar sem e-mail válido.
SEM_EMAIL = [
    "Cavanha Law Firm",
    "David Bateson",
    "Drummond Consultoria Cpa Ltda",
    "Leonardo Chaves de Campos",
    "Oliveira Lima e Dall'acqua Advogados Associados",
    "Vogler Law Offices, PC",
]


def main():
    init_db()
    db = SessionLocal()
    criados = atualizados = 0
    try:
        for nome, email in PARCEIROS:
            existing = db.query(TestemunhaDB).filter(TestemunhaDB.email == email).first()
            if existing:
                existing.nome = nome
                existing.ativo = True
                atualizados += 1
                print(f"[atualizado] {nome} <{email}>")
            else:
                db.add(
                    TestemunhaDB(
                        nome=nome,
                        email=email,
                        ativo=True,
                        created_by="seed",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                criados += 1
                print(f"[criado]     {nome} <{email}>")

        db.commit()

        print(f"\nOK. Criados={criados} Atualizados={atualizados}")
        if SEM_EMAIL:
            print(f"\nSem e-mail na exportação, não cadastrados ({len(SEM_EMAIL)}):")
            for nome in SEM_EMAIL:
                print(f"  - {nome}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
