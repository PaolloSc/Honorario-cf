"""Textos: concordancia do aditivo (item/clausula) e 'lhe(s) foram conferidos' no substabelecimento."""
import pytest

from app.models.documentos_complementares import AlteracaoClausula
from app.services.complementares_generator import AditivoGenerator
from tests.test_documentos_complementares import (  # noqa: F401  (auth_e_origem e' fixture autouse)
    PROC_A,
    SUBSTABELECIMENTO,
    _id,
    _texto,
    auth_e_origem,
)


@pytest.mark.parametrize("tipo,clausula,esperado", [
    ("alterar", "Cláusula 3ª, item 3.2", "Fica alterada a Cláusula 3ª, item 3.2, que passa"),
    ("alterar", "item 3.2", "Fica alterado o item 3.2, que passa"),
    ("alterar", "Item 3.2", "Fica alterado o Item 3.2, que passa"),
    ("alterar", "parágrafo único", "Fica alterado o parágrafo único, que passa"),
    ("alterar", "alínea b", "Fica alterada a alínea b, que passa"),
    ("alterar", "3.2", "Fica alterada a disposição 3.2, que passa"),
    ("excluir", "Cláusula 5ª", "Fica excluída a Cláusula 5ª do contrato original."),
    ("excluir", "item 5.1", "Fica excluído o item 5.1 do contrato original."),
])
def test_aditivo_concorda_com_o_que_foi_digitado(tipo, clausula, esperado):
    alt = AlteracaoClausula(tipo=tipo, clausula=clausula, texto="novo" if tipo == "alterar" else None)
    assert esperado in AditivoGenerator._redacao_alteracao(alt)


def _sub(substabelecentes):
    return {**SUBSTABELECIMENTO, "processos": [PROC_A], "substabelecentes": substabelecentes}


def test_lhe_no_singular_com_um_substabelecente(client):
    um = [SUBSTABELECIMENTO["substabelecentes"][0]]
    texto = _texto(client, _id(client, "substabelecimento", _sub(um)))
    assert "os poderes que lhe foram conferidos por" in texto and "lhes foram" not in texto


def test_lhes_no_plural_com_dois_ou_mais_substabelecentes(client):
    texto = _texto(client, _id(client, "substabelecimento", _sub(SUBSTABELECIMENTO["substabelecentes"])))
    assert "os poderes que lhes foram conferidos por" in texto and "lhe foram" not in texto
