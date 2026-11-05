"""Se o gerador falha na edicao/reversao, a copia _vN da versao atual nao fica orfa e nada vai ao banco."""
from app.database import ContractVersionDB, SessionLocal
from app.services.contract_dispatch import get_generator
from tests.test_documentos_complementares import DISTRATO, _gerar, auth_e_origem  # noqa: F401  (fixture autouse)
from tests.test_substabelecimento_regerar import _docx_no_disco, _form, _versao


def _caminhos(contract_id: str) -> dict[int, str]:
    db = SessionLocal()
    try:
        vs = db.query(ContractVersionDB).filter_by(contract_id=contract_id).all()
        return {v.version_number: v.file_path for v in vs}
    finally:
        db.close()


def _quebrar_gerador(monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError("falha ao gerar")

    monkeypatch.setattr(get_generator("distrato").__class__, "generate", quebra)


def test_put_com_falha_no_generate_nao_deixa_copia_nem_versao(client, monkeypatch):
    cid = _gerar(client, "distrato", DISTRATO).json()["contract_id"]
    arquivos, caminhos = _docx_no_disco(), _caminhos(cid)
    _quebrar_gerador(monkeypatch)
    resp = client.put(f"/api/contracts/{cid}", json={"form_data": _form(cid)})
    monkeypatch.undo()
    assert resp.status_code == 500 and "falha ao gerar" not in resp.text
    assert _docx_no_disco() == arquivos  # sem contrato_<id>_v1.docx sobrando
    assert _versao(cid) == 1 and _caminhos(cid) == caminhos


def test_reverter_com_falha_no_generate_nao_deixa_copia_nem_versao(client, monkeypatch):
    cid = _gerar(client, "distrato", DISTRATO).json()["contract_id"]
    assert client.put(f"/api/contracts/{cid}", json={"form_data": _form(cid)}).status_code == 200
    arquivos, caminhos = _docx_no_disco(), _caminhos(cid)
    _quebrar_gerador(monkeypatch)
    resp = client.post(f"/api/contracts/{cid}/rollback", params={"version": 1})
    monkeypatch.undo()
    assert resp.status_code == 500 and "falha ao gerar" not in resp.text
    assert _docx_no_disco() == arquivos
    assert _versao(cid) == 2 and _caminhos(cid) == caminhos
