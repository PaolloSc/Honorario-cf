"""Admin: upload e gerenciamento de credencial PBH."""
from __future__ import annotations

from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models.nfse import CredencialPbhCreate, CredencialPbhOut
from app.services.crypto import CryptoBox


router = APIRouter(prefix="/api/admin/credencial-pbh", tags=["admin-nfse"])


def _require_admin(user=Depends(get_current_user)):
    if (user.get("role") if isinstance(user, dict) else getattr(user, "role", None)) != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas admin")
    return user


def _ensure_enabled() -> None:
    if not settings.nfse_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NFS-e desabilitado")
    if not settings.nfse_kek:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "NFSE_KEK nao configurada")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


@router.post("", response_model=CredencialPbhOut, status_code=201)
def upsert_credencial(
    body: CredencialPbhCreate,
    db: Session = Depends(get_db),
    user=Depends(_require_admin),
):
    _ensure_enabled()
    cnpj = _digits(body.cnpj_prestador)
    if len(cnpj) != 14:
        raise HTTPException(400, "CNPJ invalido")

    box = CryptoBox(settings.nfse_kek)
    login_blob = box.encrypt(body.login)
    senha_blob = box.encrypt(body.senha)
    now = datetime.now(timezone.utc)
    user_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", "admin")

    existing = db.execute(
        text("SELECT id FROM credencial_pbh WHERE cnpj_prestador = :c"),
        {"c": cnpj},
    ).fetchone()

    if existing:
        credencial_id = existing[0]
        db.execute(
            text("""
                UPDATE credencial_pbh
                SET login_enc=:le, nonce_login=:nl, senha_enc=:se, nonce_senha=:ns,
                    ativo=1, motivo_inativacao=NULL, atualizado_em=:now
                WHERE id=:id
            """),
            {
                "le": login_blob.ciphertext,
                "nl": login_blob.nonce,
                "se": senha_blob.ciphertext,
                "ns": senha_blob.nonce,
                "now": now,
                "id": credencial_id,
            },
        )
    else:
        db.execute(
            text("""
                INSERT INTO credencial_pbh (cnpj_prestador, login_enc, nonce_login,
                                            senha_enc, nonce_senha, ativo,
                                            criado_em, criado_por)
                VALUES (:c, :le, :nl, :se, :ns, 1, :now, :u)
            """),
            {
                "c": cnpj,
                "le": login_blob.ciphertext,
                "nl": login_blob.nonce,
                "se": senha_blob.ciphertext,
                "ns": senha_blob.nonce,
                "now": now,
                "u": user_email,
            },
        )
    db.execute(
        text("""
            INSERT INTO nfse_audit_log (acao, user_email, payload_after, ts)
            VALUES ('credencial.upsert', :u, :p, :now)
        """),
        {"u": user_email, "p": '{"cnpj_prestador":"' + cnpj + '"}', "now": now},
    )
    db.commit()

    row = db.execute(
        text("""SELECT id, cnpj_prestador, ativo, criado_em, criado_por, motivo_inativacao
                FROM credencial_pbh WHERE cnpj_prestador=:c"""),
        {"c": cnpj},
    ).fetchone()
    return CredencialPbhOut(
        id=row[0],
        cnpj_prestador=row[1],
        ativo=bool(row[2]),
        criado_em=row[3],
        criado_por=row[4],
        motivo_inativacao=row[5],
    )


@router.get("", response_model=list[CredencialPbhOut])
def listar(db: Session = Depends(get_db), user=Depends(_require_admin)):
    _ensure_enabled()
    rows = db.execute(
        text("""SELECT id, cnpj_prestador, ativo, criado_em, criado_por, motivo_inativacao
                FROM credencial_pbh ORDER BY criado_em DESC""")
    ).fetchall()
    return [
        CredencialPbhOut(
            id=row[0],
            cnpj_prestador=row[1],
            ativo=bool(row[2]),
            criado_em=row[3],
            criado_por=row[4],
            motivo_inativacao=row[5],
        )
        for row in rows
    ]


@router.post("/{cnpj}/desativar", response_model=CredencialPbhOut)
def desativar(
    cnpj: str,
    motivo: str = "",
    db: Session = Depends(get_db),
    user=Depends(_require_admin),
):
    _ensure_enabled()
    cnpj = _digits(cnpj)
    now = datetime.now(timezone.utc)
    user_email = user.get("email") if isinstance(user, dict) else getattr(user, "email", "admin")
    db.execute(
        text("""UPDATE credencial_pbh SET ativo=0, motivo_inativacao=:m, atualizado_em=:n
                WHERE cnpj_prestador=:c"""),
        {"m": motivo or "manual", "n": now, "c": cnpj},
    )
    db.execute(
        text("INSERT INTO nfse_audit_log (acao, user_email, ts) VALUES ('credencial.desativar', :u, :n)"),
        {"u": user_email, "n": now},
    )
    db.commit()
    row = db.execute(
        text("""SELECT id, cnpj_prestador, ativo, criado_em, criado_por, motivo_inativacao
                FROM credencial_pbh WHERE cnpj_prestador=:c"""),
        {"c": cnpj},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Credencial nao encontrada")
    return CredencialPbhOut(
        id=row[0],
        cnpj_prestador=row[1],
        ativo=bool(row[2]),
        criado_em=row[3],
        criado_por=row[4],
        motivo_inativacao=row[5],
    )
