"""CRUD de TaxCode (master data fiscal). Acesso: financeiro/admin."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_financeiro
from app.database import TaxCodeDB, get_db
from app.models.tax_code import TaxCodeCreate, TaxCodeOut, TaxCodeUpdate


router = APIRouter(prefix="/api/tax-codes", tags=["tax-codes"])


@router.get("", response_model=list[TaxCodeOut])
def listar(
    incluir_inativos: bool = False,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    q = db.query(TaxCodeDB)
    if not incluir_inativos:
        q = q.filter(TaxCodeDB.ativo == True)  # noqa: E712
    return q.order_by(TaxCodeDB.codigo).all()


@router.get("/default", response_model=TaxCodeOut)
def get_default(
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    tc = (
        db.query(TaxCodeDB)
        .filter(TaxCodeDB.codigo == "PADRAO_1545", TaxCodeDB.ativo == True)  # noqa: E712
        .first()
    )
    if not tc:
        raise HTTPException(404, "Tax code default 'PADRAO_1545' nao encontrado")
    return tc


@router.post("", response_model=TaxCodeOut, status_code=status.HTTP_201_CREATED)
def criar(
    body: TaxCodeCreate,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    tc = TaxCodeDB(
        codigo=body.codigo,
        descricao=body.descricao,
        aliquota_total=body.aliquota_total,
        aliquota_iss=body.aliquota_iss,
        aliquota_pis=body.aliquota_pis,
        aliquota_cofins=body.aliquota_cofins,
        aliquota_irrf=body.aliquota_irrf,
        aliquota_csll=body.aliquota_csll,
        ativo=True,
        criado_em=datetime.now(timezone.utc),
        criado_por=user.email,
    )
    db.add(tc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Codigo '{body.codigo}' ja existe")
    db.refresh(tc)
    return tc


@router.patch("/{tax_code_id}", response_model=TaxCodeOut)
def atualizar(
    tax_code_id: int,
    body: TaxCodeUpdate,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    tc = db.query(TaxCodeDB).filter(TaxCodeDB.id == tax_code_id).first()
    if not tc:
        raise HTTPException(404, "Tax code nao encontrado")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(tc, field, val)
    db.commit()
    db.refresh(tc)
    return tc


@router.post("/{tax_code_id}/desativar", response_model=TaxCodeOut)
def desativar(
    tax_code_id: int,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    tc = db.query(TaxCodeDB).filter(TaxCodeDB.id == tax_code_id).first()
    if not tc:
        raise HTTPException(404, "Tax code nao encontrado")

    ativos_count = (
        db.query(TaxCodeDB).filter(TaxCodeDB.ativo == True).count()  # noqa: E712
    )
    if tc.ativo and ativos_count <= 1:
        raise HTTPException(422, "Pelo menos um tax_code deve estar ativo")

    tc.ativo = False
    db.commit()
    db.refresh(tc)
    return tc
