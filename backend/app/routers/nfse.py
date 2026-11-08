"""Endpoints publicos NFS-e (health agora; lista/vincular nas proximas tasks)."""
from __future__ import annotations

import re
from datetime import date as _date, datetime, datetime as _dt, timedelta as _td, timezone, timezone as _tz
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import require_financeiro
from app.config import settings
from app.database import SessionLocal, get_db
from app.models.nfse import NFSeOut, VincularRequest
from app.services import notas_recebidas as notas
from app.services.nfse_pagamento import gerar_pagamento_para_nfse


router = APIRouter(prefix="/api/nfse", tags=["nfse"])


@router.get("/health")
def nfse_health() -> dict:
    """Estado da feature NFS-e. Publico, sem segredos no payload."""
    if not settings.nfse_enabled:
        return {"enabled": False}

    with SessionLocal() as db:
        last = notas.ultimo_job(db)
        ultimo = None if last is None else {
            "iniciado_em": last.iniciado_em.isoformat() if last.iniciado_em else None,
            "finalizado_em": last.finalizado_em.isoformat() if last.finalizado_em else None,
            "status": last.status,
            "total_nfs": last.total_nfs,
            "erros": last.erros,
        }

    return {
        "enabled": True,
        "last_job": ultimo,
        "now": datetime.now(timezone.utc).isoformat(),
    }


@router.get("", response_model=list[NFSeOut])
def listar_nfse(
    cnpj_prestador: Optional[str] = None,
    competencia_mes: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    status: Optional[str] = None,
    direcao: Optional[str] = Query(None, pattern=r"^(emitida|recebida)$"),
    db: Session = Depends(get_db),
    user=Depends(require_financeiro),
):
    if not settings.nfse_enabled:
        raise HTTPException(404, "NFS-e desabilitado")
    de = ate = None
    if competencia_mes:
        year, month = map(int, competencia_mes.split("-"))
        de = _date(year, month, 1)
        ate = _date(year + (month // 12), (month % 12) + 1, 1) - _td(days=1)
    rows = notas.listar(
        db, direcao=direcao, cnpj_prestador=cnpj_prestador,
        competencia_de=de, competencia_ate=ate, status=status,
    )
    return [NFSeOut.model_validate(r) for r in rows]


@router.post("/{nfse_id}/vincular", response_model=NFSeOut)
def vincular_manual(
    nfse_id: int,
    body: VincularRequest,
    db: Session = Depends(get_db),
    user=Depends(require_financeiro),
):
    if not settings.nfse_enabled:
        raise HTTPException(404, "NFS-e desabilitado")
    user_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", "?")
    try:
        nota, participacao_id = notas.vincular_manual(db, nfse_id, body.contract_id, body.motivo, user_email)
    except notas.NotaNaoEncontrada:
        raise HTTPException(404, "NFS-e nao encontrada")
    except notas.NotaNaoVinculavel as e:
        raise HTTPException(409, str(e))
    except notas.ContratoNaoExiste:
        raise HTTPException(404, "contrato nao existe")

    if participacao_id:
        gerar_pagamento_para_nfse(db, nfse_id=nfse_id)
        db.refresh(nota)
    return NFSeOut.model_validate(nota)


@router.post("/sync", response_model=dict)
def sync_manual(
    cnpj_prestador: str,
    db: Session = Depends(get_db),
    user=Depends(require_financeiro),
):
    """Registra intencao de sync manual; execucao remota fica fora deste sprint."""
    if not settings.nfse_enabled:
        raise HTTPException(404, "NFS-e desabilitado")
    cnpj = re.sub(r"\D", "", cnpj_prestador)
    now = _dt.now(_tz.utc)
    user_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", "?")
    notas.criar_job(db, cnpj, "manual", user_email, now.date(), now.date(), status="agendado")
    return {"ok": True, "msg": "sync agendado; GH Actions executara no proximo run ou via dispatch"}
