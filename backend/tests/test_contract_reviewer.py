from app.services import contract_reviewer


def test_extracts_json_array_from_prose_wrapped_response(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": 'Aqui esta a analise:\n[{"trecho": "a CONTRATANTE", '
                        '"problema": "concordancia", "sugestao": "o CONTRATANTE"}]\nFim.',
                    }
                ]
            }

    monkeypatch.setattr(contract_reviewer.settings, "deepseek_api_key", "fake-key")
    monkeypatch.setattr(contract_reviewer.httpx, "post", lambda *a, **kw: FakeResponse())

    findings = contract_reviewer.review_text("texto do contrato")

    assert findings == [
        {"trecho": "a CONTRATANTE", "problema": "concordancia", "sugestao": "o CONTRATANTE"}
    ]


def test_returns_empty_list_when_no_json_found(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"content": [{"type": "text", "text": "sem achados"}]}

    monkeypatch.setattr(contract_reviewer.settings, "deepseek_api_key", "fake-key")
    monkeypatch.setattr(contract_reviewer.httpx, "post", lambda *a, **kw: FakeResponse())

    assert contract_reviewer.review_text("texto") == []


def test_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(contract_reviewer.settings, "deepseek_api_key", "")

    try:
        contract_reviewer.review_text("texto")
        assert False, "deveria ter levantado ContractReviewError"
    except contract_reviewer.ContractReviewError:
        pass


def test_extract_open_fields_only_includes_free_text_the_user_typed():
    data = {
        "contratantes": [{"profissao": "Empresária"}],
        "escopos": [
            {
                "descricao_custom": "Assessoria para renegociação de dívidas",
                "numero_autos": "0001234-56.2024.8.13.0001",  # nao e' prosa, nao deve entrar
                "demandas": None,
                "permuta": {"descricao": "Troca por consultoria contábil"},
            }
        ],
        "acessorios": {
            "clausulas_adicionais": "As partes se comprometem a manter sigilo.",
            "criterio_extincao_exito": "",
        },
    }

    text = contract_reviewer.extract_open_fields(data)

    assert "Assessoria para renegociação de dívidas" in text
    assert "As partes se comprometem a manter sigilo." in text
    assert "Troca por consultoria contábil" in text
    assert "0001234-56.2024.8.13.0001" not in text


def test_extract_open_fields_empty_when_no_free_text_filled():
    data = {"contratantes": [{"nome": "Maria"}], "escopos": [], "acessorios": {}}

    assert contract_reviewer.extract_open_fields(data) == ""
