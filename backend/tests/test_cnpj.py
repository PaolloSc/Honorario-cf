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


def _fake_fontes(monkeypatch, atrasos: dict, respostas: dict):
    """Simula as três fontes com atraso próprio; chave = nome do parser."""
    import asyncio

    from app.routers import cnpj as cnpj_router

    async def fake_try(client, url, parser, cnpj_clean):
        await asyncio.sleep(atrasos[parser.__name__])
        return respostas.get(parser.__name__)

    monkeypatch.setattr(cnpj_router, "_try_source", fake_try)


def test_brasilapi_ganha_mesmo_chegando_por_ultimo(client, monkeypatch):
    """Só a BrasilAPI traz o QSA: perder a corrida não pode sumir com os sócios."""
    _fake_fontes(
        monkeypatch,
        {"_parse_brasilapi": 0.2, "_parse_publica_cnpj_ws": 0, "_parse_open_cnpja": 0},
        {
            "_parse_brasilapi": {"razao_social": "Brasil", "socios": [{"nome": "Ana", "qualificacao": "Sócio"}]},
            "_parse_publica_cnpj_ws": {"razao_social": "Cnpjws"},
            "_parse_open_cnpja": {"razao_social": "Cnpja"},
        },
    )
    response = client.get("/api/cnpj/00000000000191")
    assert response.status_code == 200
    assert response.json()["razao_social"] == "Brasil"


def test_brasilapi_falhando_usa_a_primeira_outra_fonte(client, monkeypatch):
    _fake_fontes(
        monkeypatch,
        {"_parse_brasilapi": 0, "_parse_publica_cnpj_ws": 0.1, "_parse_open_cnpja": 0.3},
        {"_parse_publica_cnpj_ws": {"razao_social": "Cnpjws"}, "_parse_open_cnpja": {"razao_social": "Cnpja"}},
    )
    response = client.get("/api/cnpj/00000000000191")
    assert response.status_code == 200
    assert response.json()["razao_social"] == "Cnpjws"


def test_parse_brasilapi_extrai_socios_em_title_case():
    from app.routers.cnpj import _parse_brasilapi

    data = {
        "razao_social": "EMPRESA X LTDA",
        "qsa": [
            {"nome_socio": "MARCELO PEREIRA DAS CHAGAS", "qualificacao_socio": "Sócio-Administrador",
             "cnpj_cpf_do_socio": "***752406**"},
            {"nome_socio": "", "qualificacao_socio": "Sócio"},
        ],
    }
    assert _parse_brasilapi(data, "00000000000191")["socios"] == [
        {"nome": "Marcelo Pereira das Chagas", "qualificacao": "Sócio-Administrador"}
    ]
    assert _parse_brasilapi({"razao_social": "X"}, "1")["socios"] == []
