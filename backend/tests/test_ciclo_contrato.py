"""Ciclo de vida do contrato (services/ciclo_contrato): arquivos e travamento."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.database import SessionLocal
from app.services.ciclo_contrato import Arquivos, confirmar, travado


@pytest.mark.parametrize("status,esperado", [
    ("rascunho", False), ("enviado", True), ("assinado", True), ("cancelado", False), ("recusado", False),
])
def test_travado_so_olha_o_estado_atual(status, esperado):
    assert travado(SimpleNamespace(status=status)) is esperado


def test_desfazer_apaga_o_novo_e_devolve_o_conteudo_da_versao_anterior(tmp_path):
    original = tmp_path / "contrato_x.docx"
    copia = tmp_path / "contrato_x_v1.docx"
    novo = tmp_path / "contrato_x_v2.docx"
    original.write_bytes(b"texto da v2 (gerador sobrescreveu)")
    copia.write_bytes(b"texto da v1")
    novo.write_bytes(b"v2")
    arq = Arquivos(novos=[str(novo)], congelados=[(original, copia)])

    arq.desfazer()

    assert not novo.exists() and not copia.exists()
    assert original.read_bytes() == b"texto da v1"
    arq.desfazer()  # repetir nao quebra


def test_confirmar_que_falha_desfaz_o_disco_e_repete_o_erro(tmp_path, monkeypatch):
    f = tmp_path / "contrato_y.docx"
    f.write_bytes(b"x")
    db = SessionLocal()
    monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(RuntimeError("banco fora")))
    with pytest.raises(RuntimeError):
        confirmar(db, Arquivos(novos=[str(f)]))
    db.close()
    assert not Path(f).exists()
