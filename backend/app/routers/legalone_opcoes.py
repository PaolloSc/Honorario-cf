"""Opções das tabelas do Legal One usadas na ficha do financeiro.

Leitura para qualquer usuário autenticado (o wizard precisa montar os dropdowns);
escrita restrita a admin.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user, require_admin
from app.database import LEGALONE_TIPOS_VALIDOS, LegalOneOpcaoDB, get_db, utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/legalone-opcoes", tags=["Legal One"])


class OpcaoOut(BaseModel):
    id: int
    tipo: str
    valor: str
    ativo: bool


class OpcoesResponse(BaseModel):
    """As três listas numa resposta só — o wizard carrega tudo em uma chamada."""
    categoria_cliente: list[OpcaoOut] = []
    etiqueta: list[OpcaoOut] = []
    lista_transmissao: list[OpcaoOut] = []


def _validar_tipo(tipo: str) -> str:
    if tipo not in LEGALONE_TIPOS_VALIDOS:
        raise ValueError(f"Tipo invalido. Validos: {', '.join(LEGALONE_TIPOS_VALIDOS)}")
    return tipo


class CreateOpcaoRequest(BaseModel):
    tipo: str
    valor: str = Field(..., max_length=256)  # igual a coluna; sem isso o Postgres da 500

    @field_validator("tipo")
    @classmethod
    def _tipo_valido(cls, v: str) -> str:
        return _validar_tipo(v)

    @field_validator("valor")
    @classmethod
    def _valor_nao_vazio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Valor obrigatorio")
        return v


class UpdateOpcaoRequest(BaseModel):
    ativo: bool


def _to_out(o: LegalOneOpcaoDB) -> OpcaoOut:
    return OpcaoOut(id=o.id, tipo=o.tipo, valor=o.valor, ativo=o.ativo)


@router.get("", response_model=OpcoesResponse)
def list_opcoes(
    incluir_inativos: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista as opções agrupadas por tipo. Só as ativas, salvo pedido explícito.

    Ver as inativas é assunto de admin — é o que a tela de manutenção usa, e o 403
    daqui é o que faz aquela tela mostrar "Acesso Restrito" a quem não é admin.
    """
    if incluir_inativos and user.role != "admin":
        raise HTTPException(403, "Apenas administradores veem opcoes inativas")
    q = db.query(LegalOneOpcaoDB)
    if not incluir_inativos:
        q = q.filter(LegalOneOpcaoDB.ativo.is_(True))
    rows = q.order_by(LegalOneOpcaoDB.valor).all()

    agrupado: dict[str, list[OpcaoOut]] = {tipo: [] for tipo in LEGALONE_TIPOS_VALIDOS}
    for row in rows:
        if row.tipo in agrupado:
            agrupado[row.tipo].append(_to_out(row))
    return OpcoesResponse(**agrupado)


@router.post("", response_model=OpcaoOut, status_code=201)
def create_opcao(
    body: CreateOpcaoRequest,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    o = LegalOneOpcaoDB(tipo=body.tipo, valor=body.valor, ativo=True, created_at=utcnow())
    db.add(o)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"'{body.valor}' ja existe nesta lista")
    except DataError:
        db.rollback()
        raise HTTPException(422, "Valor longo demais")
    db.refresh(o)
    logger.info("Opcao Legal One criada: %s/%s por %s", o.tipo, o.valor, admin.email)
    return _to_out(o)


@router.patch("/{opcao_id}", response_model=OpcaoOut)
def update_opcao(
    opcao_id: int,
    body: UpdateOpcaoRequest,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Ativa/desativa. Desativar some do wizard sem apagar o histórico dos contratos."""
    o = db.query(LegalOneOpcaoDB).filter(LegalOneOpcaoDB.id == opcao_id).first()
    if not o:
        raise HTTPException(404, "Opcao nao encontrada")
    o.ativo = body.ativo
    db.commit()
    db.refresh(o)
    logger.info("Opcao Legal One %s ativo=%s por %s", opcao_id, body.ativo, admin.email)
    return _to_out(o)
