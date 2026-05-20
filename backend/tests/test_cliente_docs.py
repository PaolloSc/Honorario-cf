import json

from app import database


def test_derive_cliente_docs_normalizes_and_sorts_unique_docs():
    data = {
        "contratantes": [
            {"cpf": "123.456.789-09"},
            {"cnpj": "12.345.678/0001-90"},
            {"cpf": "12345678909"},
            {"nome": "Sem documento"},
        ]
    }

    assert hasattr(database, "derive_cliente_docs")
    assert database.derive_cliente_docs(data) == ["12345678000190", "12345678909"]


def test_serialize_cliente_docs_returns_json_array():
    data = {"contratantes": [{"cnpj": "98.765.432/0001-10"}]}

    assert hasattr(database, "serialize_cliente_docs")
    serialized = database.serialize_cliente_docs(data)

    assert json.loads(serialized) == ["98765432000110"]
