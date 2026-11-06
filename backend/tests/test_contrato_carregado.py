"""Contrato carregado: a versao salva ja decodificada (tipo, request, gerador, cliente)."""
import json

import pytest

from app.database import SessionLocal
from app.services.contrato_carregado import (
    TIPO_HONORARIOS,
    carregar,
    carregar_versao,
    cliente_do_form_data,
    get_generator,
    tipo_da_versao,
    ultima_versao,
)
from app.services.contract_generator import ContractGenerator
from tests.test_contrato_versoes import _criar, _form, _put
from tests.test_documentos_complementares import auth_e_origem  # noqa: F401  (fixture autouse: login + banco)


def test_tipo_da_versao_cai_em_honorarios_quando_nao_ha_tipo_ou_o_json_e_ruim():
    assert tipo_da_versao(None) == TIPO_HONORARIOS
    assert tipo_da_versao("") == TIPO_HONORARIOS
    assert tipo_da_versao("{nao e json") == TIPO_HONORARIOS
    assert tipo_da_versao(json.dumps({"contratantes": []})) == TIPO_HONORARIOS
    assert tipo_da_versao(json.dumps({"tipo_contrato": "consumidor_aereo"})) == "consumidor_aereo"


def test_cliente_do_form_data_pega_o_primeiro_contratante():
    assert cliente_do_form_data({"contratantes": [{"nome": "Ana", "email": "a@x.com"}, {"nome": "B"}]}) == ("Ana", "a@x.com")
    assert cliente_do_form_data({"contratantes": [{"razao_social": "Beta Ltda", "email": "b@x.com"}]}) == ("Beta Ltda", "b@x.com")
    assert cliente_do_form_data({"contratantes": [{}]}) == ("", "")
    assert cliente_do_form_data({"contratantes": []}) == ("", "")
    assert cliente_do_form_data({}) == ("", "")


def test_carregar_devolve_tipo_request_gerador_e_cliente_da_versao_mais_nova(client):
    cid = _criar(client)
    assert _put(client, cid, _form(valor=200)).status_code == 200

    db = SessionLocal()
    try:
        atual = carregar(db, cid)
        assert atual.versao.version_number == 2
        assert atual.tipo == TIPO_HONORARIOS
        assert atual.request.escopos[0].pro_labore.valor_total == 200
        assert isinstance(atual.gerador, ContractGenerator)
        assert atual.gerador is get_generator()
        assert atual.cliente == ("Fulano de Tal", "a@a.com")
        # versao pedida; contrato ou versao inexistente
        assert carregar(db, cid, numero=1).request.escopos[0].pro_labore.valor_total == 100
        assert carregar(db, cid, numero=9) is None
        assert carregar(db, "nao-existe") is None
        assert ultima_versao(db, cid).version_number == 2
    finally:
        db.close()


def test_modo_estrito_recusa_o_que_o_modo_brando_regera(client):
    """Contrato antigo regera (brando); a edicao aplica as regras do contrato novo (estrito)."""
    cid = _criar(client)
    db = SessionLocal()
    try:
        ver = ultima_versao(db, cid)
        ruim = json.loads(ver.form_data_json)
        ruim["contratantes"][0]["cpf"] = "123"  # CPF invalido
        ver.form_data_json = json.dumps(ruim)
        assert carregar_versao(ver).request.contratantes[0].cpf == "123"
        with pytest.raises(Exception):
            carregar_versao(ver, estrito=True)
        db.rollback()
    finally:
        db.close()
