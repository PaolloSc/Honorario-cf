"""Sugestão de cliente recorrente: visível a todo advogado, só com a qualificação."""
import json
from datetime import timedelta

import pytest

from app.auth import CurrentUser, get_current_user
from app.database import ContractDB, ContractVersionDB, SessionLocal, serialize_cliente_docs, utcnow
from app.main import app

_usuario = {"email": "a@cf.adv.br"}

PJ = {
    "tipo": "PJ", "cnpj": "12.345.678/0001-90", "razao_social": "Padaria São João Ltda",
    "endereco": "Rua A, 1", "email": "pj@x.com", "whatsapp": "(31) 99999-0000",
    "representantes": [{"nome": "José", "cpf": "111.444.777-35", "estado_civil": "Casado(a)", "segredo": "x"}],
}
PF = {
    "tipo": "PF", "nome": "Maria Souza", "nacionalidade": "Brasileira", "cpf": "529.982.247-25",
    "profissao": "Médica", "estado_civil": "Solteiro(a)", "endereco": "Rua B, 2", "email": "m@x.com",
}
SIGILO = {
    "escopos": [{"tipo": "contencioso_representacao", "descricao": "ESCOPO-SECRETO"}],
    "honorarios": [{"tipo": "exito", "percentual": "20", "valor": "VALOR-SECRETO"}],
    "valor_total": "999999", "clausulas_extras": "CLAUSULA-SECRETA", "data_assinatura": "2026-01-01",
}


def _fake_user():
    return CurrentUser(azure_id="t", email=_usuario["email"], name="T", role="advogado")


@pytest.fixture(autouse=True)
def override_auth():
    _usuario["email"] = "a@cf.adv.br"
    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _contrato(cid, contratantes, dono, dias_atras=0, **extra):
    form = {"contratantes": contratantes, **SIGILO, **extra}
    quando = utcnow() - timedelta(days=dias_atras)
    db = SessionLocal()
    db.add(ContractDB(contract_id=cid, client_name=(contratantes[0].get("nome") or contratantes[0].get("razao_social")),
                      client_email="c@x.com", current_version=1, created_by=dono, created_at=quando,
                      updated_at=quando, cliente_docs=serialize_cliente_docs(form)))
    db.add(ContractVersionDB(contract_id=cid, version_number=1, form_data_json=json.dumps(form), created_at=quando))
    db.commit()
    db.close()


def _chaves(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _chaves(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _chaves(v)


def test_outro_advogado_acha_cliente_sem_vazar_contrato(client):
    _contrato("contrato-do-a-0001", [PJ, PF], dono="a@cf.adv.br")
    _usuario["email"] = "b@cf.adv.br"

    r = client.get("/api/clientes/sugestoes", params={"q": "padaria são"})
    assert r.status_code == 200
    [s] = r.json()["sugestoes"]
    assert s["documento"] == "12345678000190" and s["nome"] == "Padaria São João Ltda"
    assert s["contratante"]["representantes"] == [{"nome": "José", "cpf": "111.444.777-35", "estado_civil": "Casado(a)"}]

    # Busca por CPF formatado acha o 2º contratante (via cliente_docs).
    [pf] = client.get("/api/clientes/sugestoes", params={"q": "529.982"}).json()["sugestoes"]
    assert pf["contratante"] == PF

    texto = r.text + json.dumps(pf)
    for proibido in ("ESCOPO-SECRETO", "VALOR-SECRETO", "CLAUSULA-SECRETA", "999999", "contrato-do-a-0001", "segredo"):
        assert proibido not in texto
    chaves = set(_chaves(r.json())) | set(_chaves(pf))
    assert not {k for k in chaves if any(p in k for p in ("escopo", "honorario", "valor", "clausula", "contract", "percentual"))}


def test_mesmo_documento_vem_uma_vez_com_dado_mais_recente(client):
    _contrato("velho-0001", [{**PF, "endereco": "Endereço antigo"}], dono="a@cf.adv.br", dias_atras=400)
    _contrato("novo-00001", [{**PF, "endereco": "Endereço novo"}], dono="c@cf.adv.br")
    [s] = client.get("/api/clientes/sugestoes", params={"q": "maria"}).json()["sugestoes"]
    assert s["contratante"]["endereco"] == "Endereço novo"


def test_representante_legado_vira_lista():
    from app.routers.clientes import _qualificacao
    q = _qualificacao({"tipo": "PJ", "cnpj": "1", "representante_nome": "Ana", "representante_cpf": "2", "honorarios": []})
    assert q == {"tipo": "PJ", "cnpj": "1", "representantes": [{"nome": "Ana", "cpf": "2"}]}


def test_minimo_tres_caracteres_e_exige_login(client):
    assert client.get("/api/clientes/sugestoes", params={"q": "ma"}).status_code == 422
    app.dependency_overrides.pop(get_current_user, None)
    assert client.get("/api/clientes/sugestoes", params={"q": "maria"}).status_code in (401, 403)
