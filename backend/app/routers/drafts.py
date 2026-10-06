from __future__ import annotations

import json
import logging
import re
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import ContractDraftDB, get_db, utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/drafts", tags=["Drafts"])

# Rascunho parado por mais que isso é apagado no próximo GET/PUT de qualquer pessoa.
RETENCAO_DIAS = 90
# O form é só texto; passar disso é bug do cliente, não rascunho de verdade.
MAX_FORM_BYTES = 512 * 1024
_DRAFT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class DraftSummary(BaseModel):
    draft_id: str
    client_name: str
    current_step: int
    created_at: str
    updated_at: str
    expires_at: str  # quando a limpeza automática apaga, se ninguém mexer


class DraftListResponse(BaseModel):
    drafts: list[DraftSummary]


class DraftDetail(DraftSummary):
    form_data: dict


class SaveDraftRequest(BaseModel):
    form_data: dict
    current_step: int = Field(1, ge=1, le=7)
    # updated_at que o cliente conhece; se o servidor tiver outro, outra aba gravou
    # depois (409). None = primeiro salvamento desta aba.
    known_updated_at: Optional[str] = None


def _client_name(form_data: dict) -> str:
    contratantes = form_data.get("contratantes") or []
    if not contratantes or not isinstance(contratantes[0], dict):
        return ""
    first = contratantes[0]
    return (first.get("nome") or first.get("razao_social") or "").strip()[:256]


def _summary(d: ContractDraftDB) -> DraftSummary:
    return DraftSummary(
        draft_id=d.draft_id,
        client_name=d.client_name,
        current_step=d.current_step,
        created_at=d.created_at.isoformat(),
        updated_at=d.updated_at.isoformat(),
        expires_at=(d.updated_at + timedelta(days=RETENCAO_DIAS)).isoformat(),
    )


def _get_own(db: Session, draft_id: str, user: CurrentUser) -> ContractDraftDB:
    draft = db.query(ContractDraftDB).filter(ContractDraftDB.draft_id == draft_id).first()
    # 404 (e não 403) para o rascunho alheio: nem confirma que o id existe.
    if not draft or draft.owner_email != user.email:
        raise HTTPException(404, "Rascunho nao encontrado")
    return draft


def _purgar_vencidos(db: Session) -> None:
    limite = utcnow().replace(tzinfo=None) - timedelta(days=RETENCAO_DIAS)
    db.query(ContractDraftDB).filter(ContractDraftDB.updated_at < limite).delete()
    db.commit()


@router.get("", response_model=DraftListResponse)
def list_drafts(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _purgar_vencidos(db)
    rows = (
        db.query(ContractDraftDB)
        .filter(ContractDraftDB.owner_email == user.email)
        .order_by(ContractDraftDB.updated_at.desc())
        .all()
    )
    return DraftListResponse(drafts=[_summary(d) for d in rows])


@router.get("/{draft_id}", response_model=DraftDetail)
def get_draft(
    draft_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draft = _get_own(db, draft_id, user)
    return DraftDetail(**_summary(draft).model_dump(), form_data=json.loads(draft.form_data_json))


@router.put("/{draft_id}", response_model=DraftSummary)
def save_draft(
    draft_id: str,
    body: SaveDraftRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria o rascunho ou sobrescreve o existente (upsert) — o id vem do navegador.

    Concorrência otimista: com ``known_updated_at`` diferente do atual, responde 409
    em vez de sobrescrever o que outra aba gravou.
    """
    if not _DRAFT_ID_RE.match(draft_id):
        raise HTTPException(422, "draft_id invalido")

    payload = json.dumps(body.form_data, ensure_ascii=False)
    if len(payload.encode("utf-8")) > MAX_FORM_BYTES:
        raise HTTPException(413, "Rascunho grande demais")

    # Também no PUT: se ninguém abrir a lista, a retenção ainda vale.
    _purgar_vencidos(db)

    draft = db.query(ContractDraftDB).filter(ContractDraftDB.draft_id == draft_id).first()
    if draft and draft.owner_email != user.email:
        raise HTTPException(404, "Rascunho nao encontrado")
    if draft and body.known_updated_at and draft.updated_at.isoformat() != body.known_updated_at:
        # Compara a string que o próprio servidor devolveu — sem parse, sem fuso.
        raise HTTPException(409, "Rascunho alterado em outra aba ou computador")

    now = utcnow()
    if draft is None:
        draft = ContractDraftDB(
            draft_id=draft_id,
            owner_email=user.email,
            created_at=now,
        )
        db.add(draft)
    draft.client_name = _client_name(body.form_data)
    draft.current_step = body.current_step
    draft.form_data_json = payload
    draft.updated_at = now

    db.commit()
    db.refresh(draft)
    return _summary(draft)


@router.delete("/{draft_id}")
def delete_draft(
    draft_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Idempotente: apagar o que já não existe (ex.: contrato gerado em outra aba) não é erro.
    draft: Optional[ContractDraftDB] = (
        db.query(ContractDraftDB).filter(ContractDraftDB.draft_id == draft_id).first()
    )
    if draft and draft.owner_email == user.email:
        db.delete(draft)
        db.commit()
    return {"success": True}
