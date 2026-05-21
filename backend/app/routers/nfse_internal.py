"""Endpoints do worker (GitHub Actions). Bearer token NFSE_WORKER_TOKEN."""
from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.nfse import IngestRequest, SyncJobOut
from app.services.crypto import CryptoBox, EncryptedBlob, InvalidCipherError
from app.services.nfse_sync import JobLockError, ingest_payload


router = APIRouter(prefix="/api/nfse", tags=["nfse-internal"])


def _require_worker(authorization: str = Header(default="")):
    if not settings.nfse_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NFS-e desabilitado")
    if not settings.nfse_worker_token:
        raise HTTPException(500, "NFSE_WORKER_TOKEN nao configurado")
    expected = f"Bearer {settings.nfse_worker_token}"
    if authorization != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token invalido")
    return True


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


@router.get("/credenciais/{cnpj}")
def fetch_credencial(
    cnpj: str,
    _: bool = Depends(_require_worker),
    db: Session = Depends(get_db),
):
    cnpj = _digits(cnpj)
    row = db.execute(
        text("""SELECT login_enc, nonce_login, senha_enc, nonce_senha, ativo
                FROM credencial_pbh WHERE cnpj_prestador=:c"""),
        {"c": cnpj},
    ).fetchone()
    if not row:
        raise HTTPException(404, "credencial nao encontrada")
    login_enc, nonce_login, senha_enc, nonce_senha, ativo = row
    if not ativo:
        raise HTTPException(409, "credencial inativa")

    box = CryptoBox(settings.nfse_kek)
    try:
        login = box.decrypt(EncryptedBlob(nonce=nonce_login, ciphertext=login_enc))
        senha = box.decrypt(EncryptedBlob(nonce=nonce_senha, ciphertext=senha_enc))
    except InvalidCipherError as e:
        raise HTTPException(500, f"falha decrypt: {e}") from e
    return {"login": login, "senha": senha}


@router.post("/ingest", response_model=SyncJobOut)
def ingest(
    body: IngestRequest,
    _: bool = Depends(_require_worker),
    db: Session = Depends(get_db),
):
    cnpj = _digits(body.cnpj_prestador)
    try:
        xmls = [base64.b64decode(item) for item in body.xmls_b64]
    except binascii.Error as e:
        raise HTTPException(400, f"xml base64 invalido: {e}") from e

    try:
        ingest_payload(
            db,
            cnpj_prestador=cnpj,
            periodo_inicio=body.periodo_inicio,
            periodo_fim=body.periodo_fim,
            origem=body.origem,
            disparado_por=body.disparado_por,
            xmls=xmls,
        )
    except JobLockError as e:
        raise HTTPException(409, str(e)) from e

    last = db.execute(
        text("SELECT * FROM sync_jobs WHERE cnpj_prestador=:c ORDER BY id DESC LIMIT 1"),
        {"c": cnpj},
    ).fetchone()
    data = last._mapping
    return SyncJobOut(
        id=data["id"],
        cnpj_prestador=data["cnpj_prestador"],
        origem=data["origem"],
        iniciado_em=data["iniciado_em"],
        finalizado_em=data["finalizado_em"],
        periodo_inicio=data["periodo_inicio"],
        periodo_fim=data["periodo_fim"],
        total_nfs=data["total_nfs"],
        auto_vinculadas=data["auto_vinculadas"],
        pendentes=data["pendentes"],
        sem_match=data["sem_match"],
        erros=data["erros"],
        status=data["status"],
        motivo_falha=data["motivo_falha"],
    )


@router.post("/sync-status")
def report_status(
    cnpj_prestador: str,
    status: str,
    motivo: str | None = None,
    _: bool = Depends(_require_worker),
    db: Session = Depends(get_db),
):
    """Worker reporta falhas pre-ingest (login, captcha, layout)."""
    cnpj = _digits(cnpj_prestador)
    now = datetime.now(timezone.utc)
    db.execute(
        text("""
            INSERT INTO sync_jobs (cnpj_prestador, origem, iniciado_em, finalizado_em,
                                   periodo_inicio, periodo_fim, status, motivo_falha)
            VALUES (:c, 'cron', :n, :n, :n, :n, :s, :m)
        """),
        {"c": cnpj, "n": now, "s": status, "m": motivo},
    )
    if status == "erro_login":
        db.execute(
            text("""UPDATE credencial_pbh
                    SET ativo=0, motivo_inativacao=:m, atualizado_em=:n
                    WHERE cnpj_prestador=:c"""),
            {"m": motivo or "login_invalido", "n": now, "c": cnpj},
        )
    db.commit()
    return {"ok": True}
