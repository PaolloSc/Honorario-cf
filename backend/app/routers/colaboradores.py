"""CRUD do roster de colaboradores (advogados/sócios/etc.). Admin only."""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin
from app.database import PAPEIS_VALIDOS, ColaboradorDB, get_db, utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/colaboradores", tags=["Colaboradores"])

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


class ColaboradorOut(BaseModel):
    id: int
    nome: str
    email: str | None
    papel: str
    ativo: bool
    ordem: int
    participavel: bool
    created_at: str


class ColaboradoresResponse(BaseModel):
    colaboradores: list[ColaboradorOut]


def _validar_papel(papel: str) -> str:
    if papel not in PAPEIS_VALIDOS:
        raise ValueError(f"Papel invalido. Validos: {', '.join(PAPEIS_VALIDOS)}")
    return papel


def _validar_email_opcional(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if not _EMAIL_RE.match(v):
        raise ValueError("Email invalido")
    return v


class CreateColaboradorRequest(BaseModel):
    nome: str
    email: str | None = None
    papel: str = "advogado"
    ordem: int = 0

    @field_validator("nome")
    @classmethod
    def _nome_nao_vazio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Nome obrigatorio")
        return v

    @field_validator("papel")
    @classmethod
    def _papel_valido(cls, v: str) -> str:
        return _validar_papel(v)

    @field_validator("email")
    @classmethod
    def _email_valido(cls, v: str | None) -> str | None:
        return _validar_email_opcional(v)


class UpdateColaboradorRequest(BaseModel):
    nome: str | None = None
    email: str | None = None
    papel: str | None = None
    ativo: bool | None = None
    ordem: int | None = None

    @field_validator("papel")
    @classmethod
    def _papel_valido(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validar_papel(v)

    @field_validator("email")
    @classmethod
    def _email_valido(cls, v: str | None) -> str | None:
        return _validar_email_opcional(v)


def _to_out(c: ColaboradorDB) -> ColaboradorOut:
    return ColaboradorOut(
        id=c.id,
        nome=c.nome,
        email=c.email,
        papel=c.papel,
        ativo=c.ativo,
        ordem=c.ordem,
        participavel=c.participavel,
        created_at=c.created_at.isoformat(),
    )


@router.get("", response_model=ColaboradoresResponse)
def list_colaboradores(
    include_inactive: bool = Query(True),
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista o roster completo (admin). Por padrão inclui inativos."""
    q = db.query(ColaboradorDB)
    if not include_inactive:
        q = q.filter(ColaboradorDB.ativo.is_(True))
    rows = q.order_by(ColaboradorDB.ordem, ColaboradorDB.nome).all()
    return ColaboradoresResponse(colaboradores=[_to_out(c) for c in rows])


@router.post("", response_model=ColaboradorOut, status_code=201)
def create_colaborador(
    body: CreateColaboradorRequest,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = ColaboradorDB(
        nome=body.nome,
        email=body.email,
        papel=body.papel,
        ativo=True,
        ordem=body.ordem,
        created_by=admin.email,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    logger.info("Colaborador criado: %s (%s) por %s", c.nome, c.papel, admin.email)
    return _to_out(c)


@router.patch("/{colaborador_id}", response_model=ColaboradorOut)
def update_colaborador(
    colaborador_id: int,
    body: UpdateColaboradorRequest,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Edita nome/email/papel/ordem ou ativa/desativa (soft delete via ativo=False)."""
    c = db.query(ColaboradorDB).filter(ColaboradorDB.id == colaborador_id).first()
    if not c:
        raise HTTPException(404, "Colaborador nao encontrado")

    if body.nome is not None:
        nome = body.nome.strip()
        if not nome:
            raise HTTPException(422, "Nome nao pode ser vazio")
        c.nome = nome
    if body.email is not None:
        c.email = body.email
    if body.papel is not None:
        c.papel = body.papel
    if body.ativo is not None:
        c.ativo = body.ativo
    if body.ordem is not None:
        c.ordem = body.ordem

    db.commit()
    db.refresh(c)
    logger.info("Colaborador %s atualizado por %s", colaborador_id, admin.email)
    return _to_out(c)


@router.delete("/{colaborador_id}")
def delete_colaborador(
    colaborador_id: int,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Soft delete: marca ativo=False (mantém histórico)."""
    c = db.query(ColaboradorDB).filter(ColaboradorDB.id == colaborador_id).first()
    if not c:
        raise HTTPException(404, "Colaborador nao encontrado")
    c.ativo = False
    db.commit()
    logger.info("Colaborador %s desativado por %s", colaborador_id, admin.email)
    return {"success": True, "id": colaborador_id, "ativo": False}
