"""Campos livres da #109 passam pelo revisor junto com a frase do contrato em que
entram, para a sugestão se encaixar nela. Sem chamada real à DeepSeek."""
from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services import contract_reviewer
from tests.test_contract_generator_fidelidade import _base_req, _escopo

DESCONTO = {
    "tem_desconto": True, "desconto_tipo": "percentual", "desconto_percentual": 10,
    "desconto_condicao": "pagamento até a data de vencimento.",
}


def _req() -> dict:
    pl = _escopo("pro_labore")
    pl["pro_labore"].update(tipo_parcelamento="customizado",
                            parcelamento_customizado="50% na assinatura e 50% em 30 dias",
                            **DESCONTO)
    ex = _escopo("exito", tipo="consultoria_contratual")
    ex["exito"].update(vencimento="10 dias após o recebimento do Benefício",
                       forma_parcelamento="em até 3 parcelas mensais",
                       tem_desconto=True, desconto_tipo="livre",
                       desconto_livre="desconto de R$ 500,00 na primeira parcela")
    req = _base_req()
    req["escopos"] = [pl, ex]
    return req


def _linhas_com_contexto(texto: str) -> dict[str, str]:
    """{linha do campo: frase de contexto logo abaixo}."""
    linhas = texto.splitlines()
    return {
        linhas[i - 1]: linha.removeprefix("  Frase no contrato: ")
        for i, linha in enumerate(linhas)
        if linha.startswith("  Frase no contrato: ")
    }


def test_campos_livres_extraidos_com_a_frase_do_contrato():
    from app.models.contract import ContratoRequest

    texto = contract_reviewer.extract_open_fields(ContratoRequest(**_req()).model_dump(mode="json"))
    ctx = _linhas_com_contexto(texto)

    assert ctx["Escopo 1 - pró-labore: condição do desconto: pagamento até a data de vencimento."] == (
        "Será concedido desconto de 10% (dez por cento) sobre estes honorários, "
        "condicionado ao seguinte: pagamento até a data de vencimento."
    )
    assert ctx["Escopo 1 - pró-labore: parcelamento customizado: 50% na assinatura e 50% em 30 dias"] == (
        "Os honorários pró-labore, no valor total de R$ 10.000,00 (dez mil reais), serão "
        "pagos da seguinte forma: 50% na assinatura e 50% em 30 dias."
    )
    assert ctx["Escopo 2 - êxito: vencimento: 10 dias após o recebimento do Benefício"].startswith(
        "Os honorários de êxito serão pagos"
    )
    assert ctx["Escopo 2 - êxito: forma de parcelamento: em até 3 parcelas mensais"] == (
        "Os honorários de êxito serão parcelados da seguinte forma: em até 3 parcelas mensais."
    )
    # O revisor vê a redundância: a frase já diz "desconto", o campo repete.
    assert ctx["Escopo 2 - êxito: especificação do desconto: desconto de R$ 500,00 na primeira parcela"] == (
        "Será concedido desconto sobre estes honorários nos seguintes termos: "
        "desconto de R$ 500,00 na primeira parcela."
    )


def test_campo_sem_frase_montavel_vai_sem_contexto():
    # Dado incompleto (pró-labore sem valor_total) não derruba a revisão.
    texto = contract_reviewer.extract_open_fields({"escopos": [{"pro_labore": {
        "parcelamento_customizado": "metade agora", "tem_desconto": True,
        "desconto_condicao": "à vista"}}]})
    assert "Escopo 1 - pró-labore: parcelamento customizado: metade agora" in texto
    assert "Frase no contrato" not in texto


def test_contexto_e_instrucao_chegam_ao_revisor(monkeypatch, client):
    enviado = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"content": [{"type": "text", "text": "[]"}]}

    def fake_post(url, json, headers, timeout):
        enviado.update(json)
        return FakeResponse()

    monkeypatch.setattr(contract_reviewer.settings, "deepseek_api_key", "fake-key")
    monkeypatch.setattr(contract_reviewer.httpx, "post", fake_post)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="user"
    )
    try:
        r = client.post("/api/contract/review", json=_req())
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200 and r.json()["enabled"] is True
    conteudo = enviado["messages"][0]["content"]
    assert "parcelamento customizado: 50% na assinatura e 50% em 30 dias\n  Frase no contrato: " in conteudo
    assert "Frase no contrato:" in enviado["system"]
    assert "NUNCA cite trecho dela" in enviado["system"]
