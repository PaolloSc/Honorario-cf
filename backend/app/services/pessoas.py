"""Pessoas do escritorio: consultas ao cadastro de colaboradores num lugar so'.

Antes, o roteador de usuarios e o servico de assinatura montavam cada um a sua consulta
(socio ativo por e-mail, lista de socios, lista do wizard). Aqui ficam as perguntas;
quem chama so' decide o que fazer com a resposta.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import PAPEIS_PARTICIPAVEIS, ColaboradorDB


def listar_colaboradores(
    db: Session, *, so_participaveis: bool = False, incluir_inativos: bool = False
) -> list[ColaboradorDB]:
    q = db.query(ColaboradorDB)
    if not incluir_inativos:
        q = q.filter(ColaboradorDB.ativo.is_(True))
    if so_participaveis:
        q = q.filter(ColaboradorDB.papel.in_(PAPEIS_PARTICIPAVEIS))
    return q.order_by(ColaboradorDB.ordem, ColaboradorDB.nome).all()


def colaborador_ativo_por_email(db: Session, email: str) -> ColaboradorDB | None:
    return (
        db.query(ColaboradorDB)
        .filter(func.lower(ColaboradorDB.email) == (email or "").strip().lower(), ColaboradorDB.ativo.is_(True))
        .first()
    )


def eh_socio_ativo(db: Session, email: str) -> bool:
    c = colaborador_ativo_por_email(db, email) if (email or "").strip() else None
    return c is not None and c.papel == "socio"


def socios_ativos_com_email(db: Session) -> list[ColaboradorDB]:
    return (
        db.query(ColaboradorDB)
        .filter(ColaboradorDB.papel == "socio", ColaboradorDB.ativo.is_(True), ColaboradorDB.email.isnot(None))
        .all()
    )
