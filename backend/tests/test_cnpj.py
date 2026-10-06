def test_cnpj_invalid_format(client):
    """CNPJ with wrong length should return 400 or 404."""
    response = client.get("/api/cnpj/123")
    assert response.status_code in (400, 404, 422)


def test_cnpj_valid_format(client):
    """CNPJ with correct length should attempt lookup (may fail with no network)."""
    response = client.get("/api/cnpj/00000000000191")
    # Either returns data or 404/500 (network dependent)
    assert response.status_code in (200, 404, 500)


def test_cnpj_alfanumerico_passa_da_validacao_de_formato(client, monkeypatch):
    """Letras não podem ser apagadas antes da consulta (CNPJ alfanumérico, jul/2026)."""
    from app.routers import cnpj as cnpj_router

    chamadas: list[str] = []

    async def fake_try(client, url, parser, cnpj_clean):
        chamadas.append(cnpj_clean)
        return {"razao_social": "EMPRESA TESTE", "endereco": "Rua X"}

    monkeypatch.setattr(cnpj_router, "_try_source", fake_try)
    response = client.get("/api/cnpj/12.abc.34501de-35")
    assert response.status_code == 200
    assert chamadas and set(chamadas) == {"12ABC34501DE35"}
