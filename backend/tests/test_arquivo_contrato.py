"""Arquivo do contrato: resolvedor unico com versao.

Erro A: o DOCX provisorio ("em processamento") ficava gravado como o arquivo da versao e
passava a ser servido e enviado para assinatura. Erro B: baixar uma versao antiga regerava
o arquivo por cima do nome da versao atual.
"""
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import ContractDB, ContractVersionDB, SessionLocal, utcnow
from app.main import app
from app.services.arquivo_contrato import ArquivoNaoEncontrado, resolve_backend_path, resolver_arquivo
from app.services.contract_generator import ContractGenerator

FORM = {
    "contratantes": [{
        "tipo": "PF", "nome": "Fulano", "nacionalidade": "brasileiro",
        "cpf": "00000000000", "profissao": "x", "estado_civil": "Solteiro(a)",
        "endereco": "rua x", "email": "a@a.com",
    }],
    "escopos": [{"tipo": "consultoria_lgpd", "honorarios": ["pro_labore"],
                 "pro_labore": {"valor_total": 10000, "tem_parcelamento": False}}],
    "acessorios": {"tem_reembolso": True, "reembolso_limitado": False,
                   "tem_penalidade_inadimplemento": False},
    "participacao": {"tem_participacao": False},
}


def _texto(path) -> str:
    from docx import Document

    return "\n".join(p.text for p in Document(str(path)).paragraphs)


def _saida() -> Path:
    d = resolve_backend_path(settings.output_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _contrato(versoes: dict[int, str | None], atual: int) -> str:
    """Cria um contrato com as versoes dadas {numero: file_path}."""
    cid = str(uuid.uuid4())
    db = SessionLocal()
    db.add(ContractDB(contract_id=cid, status="rascunho", client_name="Fulano", client_email="a@a.com",
                      current_version=atual, created_by="lawyer@test.com",
                      created_at=utcnow(), updated_at=utcnow()))
    for n, caminho in versoes.items():
        db.add(ContractVersionDB(contract_id=cid, version_number=n, form_data_json=json.dumps(FORM),
                                 file_path=caminho, created_at=utcnow()))
    db.commit()
    db.close()
    return cid


@pytest.fixture
def advogado():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="advogado")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_erro_a_provisorio_nao_vira_o_arquivo_da_versao(client, advogado):
    cid = _contrato({1: str(_saida() / f"contrato_{cid_morto()}.docx")}, atual=1)
    sem_modelo = patch.object(ContractGenerator, "generate", side_effect=FileNotFoundError("modelo"))

    with sem_modelo:
        r = client.get(f"/api/contract/{cid}/download")
        assert r.status_code == 200  # a tela continua recebendo o aviso de "em processamento"
        # envio para assinatura / e-mail: nunca com o provisorio
        with SessionLocal() as db, pytest.raises(ArquivoNaoEncontrado):
            resolver_arquivo(cid, db)

    # o provisorio nao ficou gravado: com o modelo de volta, o download traz o contrato de verdade
    r = client.get(f"/api/contract/{cid}/download")
    assert r.status_code == 200
    with SessionLocal() as db:
        real = resolver_arquivo(cid, db)
    assert "SERVIÇOS ADVOCATÍCIOS" in _texto(real)
    assert "em processamento" not in _texto(real)


def test_erro_b_baixar_versao_antiga_nao_mexe_no_arquivo_da_atual(client, advogado):
    out = _saida()
    cid = _contrato({1: str(out / f"contrato_{cid_morto()}.docx"), 2: None}, atual=2)
    generico = out / f"contrato_{cid}.docx"
    generico.write_bytes(b"TEXTO-DA-VERSAO-2")  # arquivo da versao atual (com edicoes)
    with SessionLocal() as db:
        db.query(ContractVersionDB).filter_by(contract_id=cid, version_number=2).update({"file_path": str(generico)})
        db.commit()

    r = client.get(f"/api/contract/{cid}/download?version=1")  # v1 sumiu do disco: e' regerada
    assert r.status_code == 200

    assert generico.read_bytes() == b"TEXTO-DA-VERSAO-2"
    with SessionLocal() as db:
        v1 = db.query(ContractVersionDB).filter_by(contract_id=cid, version_number=1).one()
        assert Path(v1.file_path).name == f"contrato_{cid}_v1.docx"
        assert "SERVIÇOS ADVOCATÍCIOS" in _texto(v1.file_path)


def test_versao_inexistente_continua_404(client, advogado):
    cid = _contrato({1: None}, atual=1)
    r = client.get(f"/api/contract/{cid}/download?version=9")
    assert r.status_code == 404 and "Versao 9" in r.json()["detail"]


def cid_morto() -> str:
    return str(uuid.uuid4())


def test_erro_do_docuseal_nao_devolve_o_corpo_da_resposta_ao_usuario():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from app.services.docuseal import DocuSealService

    resposta = MagicMock(status_code=422, text="SEGREDO-DO-CORPO-DA-RESPOSTA")
    svc = DocuSealService.__new__(DocuSealService)
    with patch("httpx.AsyncClient") as cli:
        cli.return_value.__aenter__.return_value.post = AsyncMock(return_value=resposta)
        svc.base_url, svc.api_key = "http://x", "k"
        r = asyncio.run(svc.send_for_signature(template_id=1, signatarios=[], send_email=False))
    assert r["success"] is False and "SEGREDO" not in r["message"] and "422" in r["message"]
