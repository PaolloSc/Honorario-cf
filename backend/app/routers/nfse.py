"""Endpoints publicos NFS-e (health agora; lista/vincular nas proximas tasks)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal


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
