"""Link de convidado: token certo entra com o perfil de CONVITE_ROLE (admin), errado cai no 401 do Azure."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import auth as auth_mod
from app.config import settings
from app.database import SessionLocal


def _req(bearer: str):
    return SimpleNamespace(method="POST", headers={"Authorization": f"Bearer {bearer}"})


def test_convite(monkeypatch):
    monkeypatch.setattr(settings, "convite_token", "segredo-convite")
    monkeypatch.setattr(settings, "dev_mode", False)
    db = SessionLocal()
    try:
        db.add(auth_mod.UserDB(azure_id="a", email="a@e", name="A", role="admin", created_at=auth_mod.utcnow()))
        db.commit()
        u = auth_mod.get_current_user(_req("segredo-convite"), db)
        assert (u.email, u.role) == (auth_mod.CONVITE_EMAIL, "admin")
        assert db.query(auth_mod.UserDB).filter_by(azure_id=auth_mod.CONVITE_AZURE_ID).count() == 0  # nao grava no banco

        monkeypatch.setattr(settings, "convite_role", "advogado")  # troca pela env, sem mexer no banco
        assert auth_mod.get_current_user(_req("segredo-convite"), db).role == "advogado"

        with pytest.raises(HTTPException) as e:
            auth_mod.get_current_user(_req("segredo-errado"), db)
        assert e.value.status_code in (401, 503)

        monkeypatch.setattr(settings, "convite_token", "")  # desligado: string vazia nao entra
        with pytest.raises(HTTPException):
            auth_mod.get_current_user(_req(""), db)
    finally:
        db.close()


def test_me_do_convidado_responde_sem_linha_no_banco(client, monkeypatch):
    monkeypatch.setattr(settings, "convite_token", "segredo-convite")
    monkeypatch.setattr(settings, "convite_role", "advogado")
    monkeypatch.setattr(settings, "dev_mode", False)
    r = client.get("/api/users/me", headers={"Authorization": "Bearer segredo-convite"})
    assert r.status_code == 200
    corpo = r.json()
    assert (corpo["id"], corpo["role"], corpo["email"]) == (0, "advogado", auth_mod.CONVITE_EMAIL)
