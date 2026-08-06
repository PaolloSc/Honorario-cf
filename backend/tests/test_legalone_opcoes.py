"""Opcoes das tabelas do Legal One (/api/legalone-opcoes)."""
import pytest

from app.auth import CurrentUser, get_current_user
from app.main import app


def _admin():
    return CurrentUser(azure_id="a", email="admin@cf.com", name="Admin", role="admin")


def _advogado():
    return CurrentUser(azure_id="b", email="adv@cf.com", name="Adv", role="advogado")


@pytest.fixture
def as_admin():
    app.dependency_overrides[get_current_user] = _admin
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _criar(client, tipo: str, valor: str) -> int:
    resp = client.post("/api/legalone-opcoes", json={"tipo": tipo, "valor": valor})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_get_agrupa_por_tipo_e_ordena_por_valor(client, as_admin):
    _criar(client, "etiqueta", "Zebra")
    _criar(client, "etiqueta", "Alfa")
    _criar(client, "categoria_cliente", "Corporativo")
    _criar(client, "lista_transmissao", "Newsletter")

    body = client.get("/api/legalone-opcoes").json()
    assert [o["valor"] for o in body["etiqueta"]] == ["Alfa", "Zebra"]
    assert [o["valor"] for o in body["categoria_cliente"]] == ["Corporativo"]
    assert [o["valor"] for o in body["lista_transmissao"]] == ["Newsletter"]


def test_get_esconde_inativos_por_padrao(client, as_admin):
    ativo = _criar(client, "etiqueta", "Ativa")
    inativo = _criar(client, "etiqueta", "Desligada")
    assert client.patch(
        f"/api/legalone-opcoes/{inativo}", json={"ativo": False}
    ).status_code == 200

    padrao = client.get("/api/legalone-opcoes").json()["etiqueta"]
    assert [o["id"] for o in padrao] == [ativo]

    completo = client.get("/api/legalone-opcoes?incluir_inativos=true").json()["etiqueta"]
    assert {o["id"] for o in completo} == {ativo, inativo}
    assert [o["ativo"] for o in completo if o["id"] == inativo] == [False]


def test_create_devolve_opcao_ativa(client, as_admin):
    resp = client.post(
        "/api/legalone-opcoes", json={"tipo": "categoria_cliente", "valor": "Pessoa Física"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tipo"] == "categoria_cliente"
    assert body["valor"] == "Pessoa Física"
    assert body["ativo"] is True


def test_valor_duplicado_no_mesmo_tipo_rejeitado(client, as_admin):
    _criar(client, "etiqueta", "Trabalhista")
    resp = client.post(
        "/api/legalone-opcoes", json={"tipo": "etiqueta", "valor": "Trabalhista"}
    )
    assert resp.status_code == 409


def test_mesmo_valor_em_tipos_diferentes_aceito(client, as_admin):
    _criar(client, "etiqueta", "Trabalhista")
    resp = client.post(
        "/api/legalone-opcoes", json={"tipo": "lista_transmissao", "valor": "Trabalhista"}
    )
    assert resp.status_code == 201


def test_tipo_invalido_rejeitado(client, as_admin):
    resp = client.post("/api/legalone-opcoes", json={"tipo": "inventado", "valor": "X"})
    assert resp.status_code == 422


def test_valor_vazio_rejeitado(client, as_admin):
    resp = client.post("/api/legalone-opcoes", json={"tipo": "etiqueta", "valor": "   "})
    assert resp.status_code == 422


def test_patch_alterna_ativo(client, as_admin):
    oid = _criar(client, "etiqueta", "Vai e volta")

    desligada = client.patch(f"/api/legalone-opcoes/{oid}", json={"ativo": False})
    assert desligada.status_code == 200
    assert desligada.json()["ativo"] is False

    religada = client.patch(f"/api/legalone-opcoes/{oid}", json={"ativo": True})
    assert religada.status_code == 200
    assert religada.json()["ativo"] is True
    assert [o["id"] for o in client.get("/api/legalone-opcoes").json()["etiqueta"]] == [oid]


def test_patch_404(client, as_admin):
    assert client.patch(
        "/api/legalone-opcoes/9999", json={"ativo": False}
    ).status_code == 404


def test_escrita_negada_a_nao_admin(client):
    app.dependency_overrides[get_current_user] = _advogado
    try:
        assert client.post(
            "/api/legalone-opcoes", json={"tipo": "etiqueta", "valor": "X"}
        ).status_code == 403
        assert client.patch(
            "/api/legalone-opcoes/1", json={"ativo": False}
        ).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_leitura_permitida_a_usuario_comum(client, as_admin):
    _criar(client, "etiqueta", "Visivel")
    app.dependency_overrides[get_current_user] = _advogado
    try:
        resp = client.get("/api/legalone-opcoes")
        assert resp.status_code == 200
        assert [o["valor"] for o in resp.json()["etiqueta"]] == ["Visivel"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_incluir_inativos_negado_a_nao_admin(client, as_admin):
    _criar(client, "etiqueta", "Visivel")
    app.dependency_overrides[get_current_user] = _advogado
    try:
        assert client.get(
            "/api/legalone-opcoes?incluir_inativos=true"
        ).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_valor_longo_demais_rejeitado(client, as_admin):
    # A coluna e String(256): sem o limite no request o Postgres devolveria 500.
    resp = client.post(
        "/api/legalone-opcoes", json={"tipo": "etiqueta", "valor": "A" * 257}
    )
    assert resp.status_code == 422
