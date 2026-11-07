"""Matriz papel x capacidade, sem HTTP (app/acesso.py)."""
from types import SimpleNamespace

import pytest

from app.acesso import Capacidade as C
from app.acesso import PAPEIS, PAPEIS_DEV, capacidades_do, pode, pode_acessar_contrato

U = lambda papel, email="x@cf.com": SimpleNamespace(role=papel, email=email)  # noqa: E731

MATRIZ = {
    # papel:       administrar, operar_fin, ler_fin, ver_todos
    "admin":      (True,  True,  True,  True),
    "financeiro": (False, True,  True,  False),
    "leitor":     (False, False, True,  False),
    "advogado":   (False, False, False, False),
    "inexistente": (False, False, False, False),
}


@pytest.mark.parametrize("papel", MATRIZ)
def test_matriz(papel):
    esperado = dict(zip((C.ADMINISTRAR, C.OPERAR_FINANCEIRO, C.LER_FINANCEIRO, C.VER_CONTRATOS_DE_TODOS), MATRIZ[papel]))
    for cap, ok in esperado.items():
        assert pode(U(papel), cap) is ok, (papel, cap)


def test_conjuntos_de_papeis():
    assert set(PAPEIS) == {"admin", "advogado", "financeiro", "leitor"}
    assert set(PAPEIS_DEV) == {"admin", "advogado", "financeiro"}
    assert capacidades_do("") == frozenset()


def test_contrato_do_proprio_ou_admin():
    contrato = SimpleNamespace(created_by="dono@cf.com")
    assert pode_acessar_contrato(U("advogado", "dono@cf.com"), contrato)
    assert not pode_acessar_contrato(U("advogado", "outro@cf.com"), contrato)
    assert pode_acessar_contrato(U("admin", "outro@cf.com"), contrato)
    assert not pode_acessar_contrato(U("financeiro", "outro@cf.com"), contrato)


# ── As rotas usam a politica (as dependencias duplicadas sairam) ──────────────
from app.auth import CurrentUser, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

ROTAS = [
    # (url, papeis que entram)
    ("/api/nfse", {"admin", "financeiro"}),
    ("/api/admin/credencial-pbh", {"admin"}),
    ("/api/nfse-emitidas", {"admin", "financeiro", "leitor"}),
]


@pytest.mark.parametrize("url,permitidos", ROTAS)
def test_rotas_seguem_a_matriz(client, url, permitidos):
    try:
        for papel in ("admin", "financeiro", "leitor", "advogado"):
            app.dependency_overrides[get_current_user] = lambda p=papel: CurrentUser(
                azure_id="x", email="u@cf.com", name="U", role=p)
            r = client.get(url)
            if papel in permitidos:
                assert r.status_code != 403, (url, papel, r.text)
            else:
                assert r.status_code == 403, (url, papel, r.status_code)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
