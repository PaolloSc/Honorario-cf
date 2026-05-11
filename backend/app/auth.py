from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import UserDB, get_db, utcnow

logger = logging.getLogger(__name__)

_jwks_cache: dict | None = None


@dataclass
class CurrentUser:
    azure_id: str
    email: str
    name: str
    role: str  # "advogado" | "admin"


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache

    tenant_id = settings.azure_tenant_id
    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


def _decode_token(token: str) -> dict:
    """Decode and validate Azure AD JWT token."""
    global _jwks_cache
    try:
        # First decode header to get kid
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        if not settings.azure_tenant_id:
            raise HTTPException(503, "Autenticação não configurada")

        # Production: validate with Azure AD JWKS
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're in an async context but this is a sync function
            # Use cached JWKS or fetch synchronously
            jwks = _jwks_cache
            if not jwks:
                import httpx as httpx_sync

                tenant_id = settings.azure_tenant_id
                url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
                resp = httpx_sync.get(url, timeout=10)
                resp.raise_for_status()
                jwks = resp.json()
                _jwks_cache = jwks
        else:
            jwks = asyncio.run(_get_jwks())

        # Find the right key
        rsa_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break

        if not rsa_key:
            raise ValueError(f"Key {kid} not found in JWKS")

        tenant_id = settings.azure_tenant_id
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.azure_client_id,
            issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Token invalido: {e}")
    except Exception as e:
        logger.error("Token decode error: %s", e)
        raise HTTPException(401, f"Erro de autenticacao: {e}")


def _get_or_create_user(db: Session, azure_id: str, email: str, name: str) -> UserDB:
    user = db.query(UserDB).filter(UserDB.azure_id == azure_id).first()
    if user:
        # Update name/email if changed
        if user.email != email or user.name != name:
            user.email = email
            user.name = name
            db.commit()
        return user

    # Check if first user → make admin
    user_count = db.query(UserDB).count()
    role = "admin" if user_count == 0 else "advogado"

    user = UserDB(
        azure_id=azure_id,
        email=email,
        name=name,
        role=role,
        created_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("New user created: %s (%s) - role: %s", email, name, role)
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Token de autenticacao ausente")

    token = auth_header[7:]
    payload = _decode_token(token)

    azure_id = payload.get("oid") or payload.get("sub", "")
    email = payload.get("preferred_username") or payload.get("email") or payload.get("upn", "")
    name = payload.get("name", email)

    if not azure_id or not email:
        raise HTTPException(401, "Token sem informacoes de usuario")

    user = _get_or_create_user(db, azure_id, email, name)

    return CurrentUser(
        azure_id=user.azure_id,
        email=user.email,
        name=user.name,
        role=user.role,
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(403, "Acesso restrito a administradores")
    return user
