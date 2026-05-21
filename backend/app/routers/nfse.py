"""Endpoints publicos NFS-e (health agora; lista/vincular nas proximas tasks)."""
from __future__ import annotations

import re
from datetime import date as _date, datetime, datetime as _dt, timedelta as _td, timezone, timezone as _tz
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import SessionLocal, get_db
from app.models.nfse import NFSeOut, SyncJobOut, VincularRequest
from app.services.nfse_pagamento import gerar_pagamento_para_nfse


router = APIRouter(prefix="/api/nfse", tags=["nfse"])


@router.get("/health")
def nfse_health() -> dict:
    """Estado da feature NFS-e. Publico, sem segredos no payload."""
    if not settings.nfse_enabled:
        return {"enabled": False}

    with SessionLocal() as db:
        last = db.execute(text("""
            SELECT iniciado_em, finalizado_em, status, total_nfs, erros
            FROM sync_jobs
            ORDER BY iniciado_em DESC LIMIT 1
        """)).fetchone()

    return {
        "enabled": True,
        "last_job": None if last is None else {
            "iniciado_em": last[0].isoformat() if last[0] else None,
            "finalizado_em": last[1].isoformat() if last[1] else None,
            "status": last[2],
            "total_nfs": last[3],
            "erros": last[4],
        },
        "now": datetime.now(timezone.utc).isoformat(),
    }


def _require_financeiro(user=Depends(get_current_user)):
    role = user.get("role") if isinstance(user, dict) else getattr(user, "role", None)
    if role not in ("financeiro", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito ao financeiro")
    return user


def _nfse_out(row) -> NFSeOut:
    return NFSeOut.model_validate(dict(row._mapping))


@router.get("", response_model=list[NFSeOut])
def listar_nfse(
    cnpj_prestador: Optional[str] = None,
    competencia_mes: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(_require_financeiro),
):
    if not settings.nfse_enabled:
        raise HTTPException(404, "NFS-e desabilitado")
    sql = ["SELECT * FROM nfse_recebidas WHERE 1=1"]
    params: dict = {}
    if cnpj_prestador:
        sql.append("AND cnpj_prestador = :c")
        params["c"] = cnpj_prestador
    if competencia_mes:
        year, month = map(int, competencia_mes.split("-"))
        inicio = _date(year, month, 1)
        fim = _date(year + (month // 12), (month % 12) + 1, 1) - _td(days=1)
        sql.append("AND competencia BETWEEN :i AND :f")
        params["i"] = inicio
        params["f"] = fim
    if status:
        sql.append("AND status_matching = :s")
        params["s"] = status
    sql.append("ORDER BY data_emissao DESC LIMIT 500")
    rows = db.execute(text(" ".join(sql)), params).fetchall()
    return [_nfse_out(row) for row in rows]


@router.post("/{nfse_id}/vincular", response_model=NFSeOut)
def vincular_manual(
    nfse_id: int,
    body: VincularRequest,
    db: Session = Depends(get_db),
    user=Depends(_require_financeiro),
):
    if not settings.nfse_enabled:
        raise HTTPException(404, "NFS-e desabilitado")
    row = db.execute(
        text("SELECT id, status_matching FROM nfse_recebidas WHERE id=:i"),
        {"i": nfse_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "NFS-e nao encontrada")
    if row.status_matching == "auto":
        raise HTTPException(409, "NFS-e ja vinculada automaticamente; use 'revisar'")

    contract = db.execute(
        text("SELECT contract_id FROM contracts WHERE contract_id=:c"),
        {"c": body.contract_id},
    ).fetchone()
    if not contract:
        raise HTTPException(404, "contrato nao existe")

    part = db.execute(
        text("""SELECT id FROM participacoes
                WHERE contract_id=:c AND vinculo_ativo=1 AND aprovada=1
                ORDER BY data_inicio DESC LIMIT 1"""),
        {"c": body.contract_id},
    ).fetchone()
    participacao_id = part[0] if part else None

    user_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", "?")
    now = _dt.now(_tz.utc)
    db.execute(
        text("""UPDATE nfse_recebidas
               SET contract_id=:c, participacao_id=:p, status_matching='manual',
                   motivo=:m, atualizado_em=:n WHERE id=:i"""),
        {
            "c": body.contract_id,
            "p": participacao_id,
            "m": body.motivo or "vinculo manual",
            "n": now,
            "i": nfse_id,
        },
    )
    db.execute(
        text("""INSERT INTO nfse_audit_log (nfse_id, acao, user_email, ts)
               VALUES (:i, 'nfse.vincular_manual', :u, :n)"""),
        {"i": nfse_id, "u": user_email, "n": now},
    )
    db.commit()

    if participacao_id:
        gerar_pagamento_para_nfse(db, nfse_id=nfse_id)

    out = db.execute(text("SELECT * FROM nfse_recebidas WHERE id=:i"), {"i": nfse_id}).fetchone()
    return _nfse_out(out)


@router.post("/sync", response_model=dict)
def sync_manual(
    cnpj_prestador: str,
    db: Session = Depends(get_db),
    user=Depends(_require_financeiro),
):
    """Registra intencao de sync manual; execucao remota fica fora deste sprint."""
    if not settings.nfse_enabled:
        raise HTTPException(404, "NFS-e desabilitado")
    cnpj = re.sub(r"\D", "", cnpj_prestador)
    now = _dt.now(_tz.utc)
    user_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", "?")
    db.execute(
        text("""
            INSERT INTO sync_jobs (cnpj_prestador, origem, disparado_por,
                                   iniciado_em, periodo_inicio, periodo_fim, status)
            VALUES (:c, 'manual', :u, :n, :n, :n, 'agendado')
        """),
        {"c": cnpj, "u": user_email, "n": now},
    )
    db.commit()
    return {"ok": True, "msg": "sync agendado; GH Actions executara no proximo run ou via dispatch"}
