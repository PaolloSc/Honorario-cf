"""ParticipacaoEmailRequest: novos campos + migracao, e o HTML da ficha."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.routers.email import ParticipacaoEmailRequest


@pytest.fixture
def _override_auth():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="advogado")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _enviar(client, **campos) -> dict:
    """Envia a ficha com o serviço de e-mail mockado e devolve os kwargs enviados."""
    captured: dict = {}

    async def _capture(**kwargs):
        captured.update(kwargs)
        return {"success": True, "message": "ok"}

    mock_service = MagicMock()
    mock_service.send_html_email = AsyncMock(side_effect=_capture)
    with patch("app.routers.email.get_email_service", return_value=mock_service):
        resp = client.post(
            "/api/email/send-participacao",
            json={"contract_id": "c1", "cliente_nome": "Cliente X", **campos},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    return captured


def test_request_aceita_campos_novos():
    r = ParticipacaoEmailRequest(
        contract_id="c1",
        cliente_nome="Cliente",
        valor_tipo="valor",
        valor_monetario=5000.0,
        para_quem=["Bruno", "Ana"],
        contato_financeiro_nome="Carlos",
        contato_financeiro_email="c@x.com",
        contato_financeiro_telefone="(31) 99999-0000",
    )
    assert r.valor_tipo == "valor"
    assert r.valor_monetario == 5000.0
    assert r.para_quem == ["Bruno", "Ana"]
    assert r.contato_financeiro_email == "c@x.com"


def test_request_migra_para_quem_string():
    r = ParticipacaoEmailRequest(contract_id="c1", cliente_nome="X", para_quem="Bruno")
    assert r.para_quem == ["Bruno"]


def test_request_aceita_campos_legalone():
    r = ParticipacaoEmailRequest(
        contract_id="c1",
        cliente_nome="X",
        categoria_cliente=None,
        etiquetas="Trabalhista",
        listas_transmissao=None,
    )
    assert r.categoria_cliente == ""
    assert r.etiquetas == ["Trabalhista"]
    assert r.listas_transmissao == []


def test_html_traz_linhas_do_legal_one(client, _override_auth):
    html = _enviar(
        client,
        valor_tipo="percentual",
        valor_percentual="10",
        categoria_cliente="Corporativo",
        etiquetas=["Trabalhista", "Consultivo"],
        listas_transmissao=["Newsletter", "Eventos"],
    )["html_content"]

    assert "Categoria do cliente" in html
    assert "Corporativo" in html
    assert "Etiqueta LO" in html
    assert "Trabalhista, Consultivo" in html
    assert "Lista de transmissão" in html
    assert "Newsletter, Eventos" in html


def test_html_omite_linhas_do_legal_one_quando_vazias(client, _override_auth):
    html = _enviar(client, valor_tipo="percentual", valor_percentual="10")["html_content"]

    assert "Categoria do cliente" not in html
    assert "Etiqueta LO" not in html
    assert "Lista de transmissão" not in html


def test_ficha_sem_participacao_vira_cadastro_legal_one(client, _override_auth):
    captured = _enviar(client, categoria_cliente="Corporativo")

    assert "Cadastro Legal One" in captured["html_content"]
    assert "Ficha de Participação" not in captured["html_content"]
    assert captured["subject"] == "Cadastro Legal One — Cliente X"


def test_com_participacao_mantem_titulo_de_ficha(client, _override_auth):
    captured = _enviar(
        client,
        valor_tipo="percentual",
        valor_percentual="10",
        categoria_cliente="Corporativo",
    )

    assert "Ficha de Participação" in captured["html_content"]
    assert captured["subject"] == "Ficha de Participação — Cliente X"


def test_html_escapa_valores_do_payload(client, _override_auth):
    """O endpoint aceita string arbitraria de qualquer autenticado: sem escape,
    da para embutir instrucao falsa na ficha que o financeiro recebe."""
    html = _enviar(
        client,
        cliente_nome="<b>ACME</b>",
        etiquetas=["</td></tr></table><p>Pix alterado: 123</p><table><tr><td>"],
    )["html_content"]

    assert "<p>Pix alterado: 123</p>" not in html
    assert "&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;" in html
    assert "<b>ACME</b>" not in html
    assert "&lt;b&gt;ACME&lt;/b&gt;" in html


def test_objeto_do_contrato_mantem_quebra_de_linha(client, _override_auth):
    html = _enviar(client, objeto_contrato="Linha 1\nLinha 2")["html_content"]
    assert "Linha 1<br>Linha 2" in html


def test_listas_do_legal_one_tem_teto_de_cardinalidade(client, _override_auth):
    """Sem teto, uma requisicao gera um e-mail multi-MB ao financeiro."""
    resp = client.post(
        "/api/email/send-participacao",
        json={"contract_id": "c1", "cliente_nome": "X", "etiquetas": ["A"] * 51},
    )
    assert resp.status_code == 422


def test_titulo_e_ficha_quando_so_ha_responsavel(client, _override_auth):
    """Sem valor nem base, mas com responsavel: ainda e participacao."""
    enviado = _enviar(
        client,
        responsavel_captacao="Bruno",
        categoria_cliente="Corporativo",
    )
    assert enviado["subject"] == "Ficha de Participação — Cliente X"
    assert "Ficha de Participação" in enviado["html_content"]
