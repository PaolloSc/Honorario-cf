from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import TestemunhaDB, get_db, utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/testemunhas", tags=["Testemunhas"])

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


class TestemunhaOut(BaseModel):
    id: int
    nome: str
    email: str
    ativo: bool
    created_at: str


class TestemunhasResponse(BaseModel):
    testemunhas: list[TestemunhaOut]


class CreateTestemunhaRequest(BaseModel):
    nome: str
    email: str

    @field_validator("nome")
    @classmethod
    def _nome_nao_vazio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Nome obrigatorio")
        return v

    @field_validator("email")
    @classmethod
    def _email_valido(cls, v: str) -> str:
        v = (v or "").strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Email invalido")
        return v


class UpdateTestemunhaRequest(BaseModel):
    nome: str | None = None
    email: str | None = None
    ativo: bool | None = None

    @field_validator("email")
    @classmethod
    def _email_valido(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Email invalido")
        return v


def _to_out(t: TestemunhaDB) -> TestemunhaOut:
    return TestemunhaOut(
        id=t.id,
        nome=t.nome,
        email=t.email,
        ativo=t.ativo,
        created_at=t.created_at.isoformat(),
    )


@router.get("", response_model=TestemunhasResponse)
def list_testemunhas(
    include_inactive: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista testemunhas do roster. Por padrao apenas ativas."""
    query = db.query(TestemunhaDB)
    if not include_inactive:
        query = query.filter(TestemunhaDB.ativo.is_(True))
    rows = query.order_by(TestemunhaDB.nome).all()
    return TestemunhasResponse(testemunhas=[_to_out(t) for t in rows])


@router.post("", response_model=TestemunhaOut, status_code=201)
def create_testemunha(
    body: CreateTestemunhaRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = TestemunhaDB(
        nome=body.nome,
        email=body.email,
        ativo=True,
        created_by=user.email,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    logger.info("Testemunha criada: %s (%s) por %s", t.nome, t.email, user.email)
    return _to_out(t)


@router.patch("/{testemunha_id}", response_model=TestemunhaOut)
def update_testemunha(
    testemunha_id: int,
    body: UpdateTestemunhaRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edita nome/email ou ativa/desativa (soft delete via ativo=False)."""
    t = db.query(TestemunhaDB).filter(TestemunhaDB.id == testemunha_id).first()
    if not t:
        raise HTTPException(404, "Testemunha nao encontrada")

    if body.nome is not None:
        nome = body.nome.strip()
        if not nome:
            raise HTTPException(422, "Nome nao pode ser vazio")
        t.nome = nome
    if body.email is not None:
        t.email = body.email
    if body.ativo is not None:
        t.ativo = body.ativo

    db.commit()
    db.refresh(t)
    logger.info("Testemunha %s atualizada por %s", testemunha_id, user.email)
    return _to_out(t)
