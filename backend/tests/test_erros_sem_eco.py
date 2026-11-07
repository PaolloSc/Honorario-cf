"""Erro de dados na reversao nao devolve o texto da excecao: str(ValidationError) traz input_value
(dados do cliente). O detalhe fica so no log."""
import json

from app.database import ContractVersionDB, SessionLocal
from tests.test_documentos_complementares import DISTRATO, _gerar, auth_e_origem  # noqa: F401  (fixture autouse)
from tests.test_substabelecimento_regerar import _form

SENTINELA = "SENTINELA-529.982.247-25"


def test_reverter_versao_invalida_nao_ecoa_os_dados(client):
    cid = _gerar(client, "distrato", DISTRATO).json()["contract_id"]
    assert client.put(f"/api/contracts/{cid}", json={"form_data": _form(cid)}).status_code == 200

    db = SessionLocal()
    try:
        v1 = db.query(ContractVersionDB).filter_by(contract_id=cid, version_number=1).one()
        dados = json.loads(v1.form_data_json)
        dados["data_contrato_origem"] = SENTINELA  # formato invalido -> ValidationError
        v1.form_data_json = json.dumps(dados)
        db.commit()
    finally:
        db.close()

    resp = client.post(f"/api/contracts/{cid}/rollback", params={"version": 1})
    assert resp.status_code == 422
    assert resp.json() == {"detail": "Dados da versao 1 invalidos."}
    assert SENTINELA not in resp.text
