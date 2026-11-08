"""Endpoints do worker (GitHub Actions). Bearer token NFSE_WORKER_TOKEN."""
from __future__ import annotations

import base64
import binascii
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.nfse import IngestRequest, SyncJobOut
from app.models.nfse_db import CredencialPbhDB
from app.services import notas_recebidas as notas
from app.services.crypto import CryptoBox, EncryptedBlob, InvalidCipherError
from app.services.nfse_sync import JobLockError, ingest_payload
from app.utils.documento import normalizar_doc

logger = logging.getLogger(__name__)


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


@router.get("/credenciais/{cnpj}")
def fetch_credencial(
    cnpj: str,
    _: bool = Depends(_require_worker),
    db: Session = Depends(get_db),
):
    cnpj = normalizar_doc(cnpj)
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
        logger.error("Falha ao decifrar a credencial de %s: %s", cnpj, e)
        raise HTTPException(500, "falha decrypt") from e
    return {"login": login, "senha": senha}


@router.post("/ingest", response_model=SyncJobOut)
def ingest(
    body: IngestRequest,
    _: bool = Depends(_require_worker),
    db: Session = Depends(get_db),
):
    cnpj = normalizar_doc(body.cnpj_prestador)
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
            ultimo_nsu=body.ultimo_nsu,
        )
    except JobLockError as e:
        raise HTTPException(409, str(e)) from e

    return SyncJobOut.model_validate(notas.ultimo_job(db, cnpj))


@router.get("/adn/ultimo-nsu")
def ultimo_nsu(
    cnpj: str,
    _: bool = Depends(_require_worker),
    db: Session = Depends(get_db),
):
    """Ultimo NSU do ADN ja ingerido com sucesso (0 = comecar do inicio)."""
    return {"ultimo_nsu": notas.ultimo_nsu(db, normalizar_doc(cnpj))}


@router.post("/sync-status")
def report_status(
    cnpj_prestador: str,
    status: str,
    motivo: str | None = None,
    _: bool = Depends(_require_worker),
    db: Session = Depends(get_db),
):
    """Worker reporta falhas pre-ingest (login, captcha, layout)."""
    cnpj = normalizar_doc(cnpj_prestador)
    notas.registrar_falha_do_worker(db, cnpj, status, motivo)
    if status == "erro_login":
        cred = db.query(CredencialPbhDB).filter(CredencialPbhDB.cnpj_prestador == cnpj).first()
        if cred is not None:
            cred.ativo = False
            cred.motivo_inativacao = motivo or "login_invalido"
            cred.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}
