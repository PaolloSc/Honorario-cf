from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user, require_admin
from app.database import UserDB, get_db, utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["Users"])


class UserResponse(BaseModel):
    id: int
    azure_id: str
    email: str
    name: str
    role: str
    created_at: str


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class UpdateUserRoleRequest(BaseModel):
    role: str


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.azure_id == user.azure_id).first()
    if not db_user:
        raise HTTPException(404, "Usuario nao encontrado")
    return UserResponse(
        id=db_user.id,
        azure_id=db_user.azure_id,
        email=db_user.email,
        name=db_user.name,
        role=db_user.role,
        created_at=db_user.created_at.isoformat(),
    )


@router.get("", response_model=UserListResponse)
def list_users(admin: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(UserDB).order_by(UserDB.name).all()
    return UserListResponse(
        users=[
            UserResponse(
                id=u.id,
                azure_id=u.azure_id,
                email=u.email,
                name=u.name,
                role=u.role,
                created_at=u.created_at.isoformat(),
            )
            for u in users
        ],
        total=len(users),
    )


@router.get("/lawyers", response_model=UserListResponse)
def list_lawyers(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all lawyers (advogado + admin) for signature selection. Available to any authenticated user."""
    users = db.query(UserDB).filter(UserDB.role.in_(["advogado", "admin"])).order_by(UserDB.name).all()
    return UserListResponse(
        users=[
            UserResponse(
                id=u.id,
                azure_id=u.azure_id,
                email=u.email,
                name=u.name,
                role=u.role,
                created_at=u.created_at.isoformat(),
            )
            for u in users
        ],
        total=len(users),
    )


@router.patch("/{user_id}/role")
def update_user_role(
    user_id: int,
    body: UpdateUserRoleRequest,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if body.role not in ("admin", "advogado"):
        raise HTTPException(422, "Role invalida. Validos: admin, advogado")

    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuario nao encontrado")

    user.role = body.role
    db.commit()

    logger.info("User %s role changed to %s by %s", user.email, body.role, admin.email)
    return {"success": True, "email": user.email, "role": body.role}
