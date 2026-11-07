"""CPF/CNPJ: uma so normalizacao (utils/documento.normalizar_doc), tambem para o CNPJ alfanumerico.

Antes, o substabelecimento e o distrato comparavam documentos com `so_digitos`, que apaga as
letras: '12.ABC.345/01DE-35' e '12.XYZ.345/01FG-35' viravam o mesmo '123450135'.
"""
import json
import uuid

from app.database import ContractDB, ContractVersionDB, SessionLocal, utcnow
from app.models.documentos_complementares import TIPO_SUBSTABELECIMENTO
from app.services.substabelecimento_vinculado import documento_do_outorgante, substabelecimentos_do_outorgante
from app.utils.documento import normalizar_doc

CNPJ_A = "12.ABC.345/01DE-35"
CNPJ_B = "12.XYZ.345/01FG-35"  # mesmos numeros, em posicoes/letras diferentes


def test_normalizar_doc_mantem_letras_do_cnpj_alfanumerico():
    assert normalizar_doc(CNPJ_A) == "12ABC34501DE35"
    assert normalizar_doc("12.abc.345/01de-35") == "12ABC34501DE35"
    assert normalizar_doc("123.456.789-09") == "12345678909"
    assert normalizar_doc("11.222.333/0001-81") == "11222333000181"
    assert normalizar_doc(None) == ""


def test_documento_do_outorgante_nao_apaga_letras():
    assert documento_do_outorgante({"outorgante": {"cnpj": CNPJ_A}}) == "12ABC34501DE35"
    assert documento_do_outorgante({"outorgante": {"cpf": "123.456.789-09"}}) == "12345678909"
    assert documento_do_outorgante({}) == ""


def _substabelecimento(db, cnpj: str) -> str:
    cid = str(uuid.uuid4())
    db.add(ContractDB(contract_id=cid, status="rascunho", tipo_contrato=TIPO_SUBSTABELECIMENTO,
                      client_name="Out", client_email="o@ex.com", current_version=1,
                      created_at=utcnow(), updated_at=utcnow()))
    db.add(ContractVersionDB(contract_id=cid, version_number=1, created_at=utcnow(),
                             form_data_json=json.dumps({"outorgante": {"cnpj": cnpj}})))
    db.commit()
    return cid


def test_substabelecimento_de_outro_cnpj_alfanumerico_nao_e_o_mesmo_outorgante():
    db = SessionLocal()
    try:
        a = _substabelecimento(db, CNPJ_A)
        b = _substabelecimento(db, CNPJ_B)
        achados = {c.contract_id for c in substabelecimentos_do_outorgante(db, normalizar_doc(CNPJ_A))}
        assert a in achados
        assert b not in achados
    finally:
        db.close()
