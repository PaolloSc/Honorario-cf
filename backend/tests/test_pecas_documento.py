"""Pecas dos geradores de documento: qualificacao das partes e pagina compartilhada."""
from types import SimpleNamespace

from app.models.contrato_consumidor import ContratoConsumidorRequest
from app.services.complementares_generator import AditivoGenerator, DistratoGenerator, SubstabelecimentoGenerator
from app.services.consumidor_generator import ConsumidorGenerator
from app.services.contract_generator import ContractGenerator
from app.services.pagina_documento import PaginaCompacta
from app.services.qualificacao import (
    nacionalidade,
    qualificar_do_contrato_de_origem,
    qualificar_representante,
    qualificar_substabelecido,
)


def test_nacionalidade_generica_concorda_e_estrangeira_e_preservada():
    assert nacionalidade("Brasileira (o)", True) == "brasileira"
    assert nacionalidade("", False) == "brasileiro"
    assert nacionalidade("Portuguesa", False) == "Portuguesa"


def test_qualificar_do_contrato_de_origem_pf_e_pj():
    pf = {"nome": "Ana Souza", "cpf": "1", "nacionalidade": "brasileira", "endereco": "Rua A"}
    assert qualificar_do_contrato_de_origem(pf) == "Ana Souza, brasileira, CPF n.º 1, residente em Rua A"
    pj = {"razao_social": "Acme Ltda", "cnpj": "2", "representantes": [{"nome": "Beto", "cpf": "3"}]}
    texto = qualificar_do_contrato_de_origem(pj)
    assert "inscrita no CNPJ sob o n.º 2" in texto and texto.endswith("neste ato representada por Beto, CPF 3")
    assert "representada" not in qualificar_do_contrato_de_origem(pj, com_representantes=False)


def test_qualificar_substabelecido_sem_genero_sai_neutro():
    s = SimpleNamespace(genero=None, nome="Fulano", oab="OAB/MG 1", nacionalidade="", estado_civil="")
    assert qualificar_substabelecido(s) == "Fulano, inscrito(a) na OAB/MG 1"


def test_qualificar_representante_omite_campos_vazios():
    r = SimpleNamespace(nome="Carla", nacionalidade="brasileira", profissao="", estado_civil=None, cpf="9", email=None)
    assert qualificar_representante(r) == "CARLA, brasileira, CPF 9"


def test_os_quatro_geradores_compartilham_a_pagina_sem_herdar_um_do_outro():
    for g in (ConsumidorGenerator, AditivoGenerator, DistratoGenerator, SubstabelecimentoGenerator):
        assert issubclass(g, PaginaCompacta) and issubclass(g, ContractGenerator)
    assert not issubclass(AditivoGenerator, ConsumidorGenerator)
    assert not issubclass(ConsumidorGenerator, AditivoGenerator)
