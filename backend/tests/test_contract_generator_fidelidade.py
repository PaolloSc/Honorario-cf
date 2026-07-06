"""Garante que o contrato gerado reproduz o texto do modelo oficial (seções 4-11)."""
import re
import zipfile

from app.models.contract import ContratoRequest
from app.services.contract_generator import ContractGenerator


def _paras_for(req: dict) -> list[str]:
    """Gera o contrato e devolve os parágrafos de texto do .docx."""
    data = ContratoRequest(**req)
    gen = ContractGenerator()
    _, path = gen.generate(data, contract_id="FIDELIDADE_TEST")
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    paras = []
    for p in re.split(r"</w:p>", xml):
        txt = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p))
        if txt.strip():
            paras.append(txt.replace("&amp;", "&"))
    return paras


def _base_req(*, honorario="hora_trabalhada", extra_escopo=None, partes_rel=True) -> dict:
    escopo = {"tipo": "consultoria_lgpd", "honorarios": [honorario]}
    if honorario == "hora_trabalhada":
        escopo["hora_trabalhada"] = {
            "valor_hora": 300, "tem_teto_mensal": False, "tem_pacote_horas": False,
            "tem_hora_urgencia": False, "tem_hora_fora_expediente": False,
        }
    if extra_escopo:
        escopo.update(extra_escopo)
    return {
        "contratantes": [{
            "tipo": "PF", "nome": "Fulano", "nacionalidade": "brasileiro",
            "cpf": "00000000000", "profissao": "x", "estado_civil": "Solteiro(a)",
            "endereco": "rua x", "email": "a@a.com",
        }],
        "incluir_partes_relacionadas": partes_rel,
        "escopos": [escopo],
        "acessorios": {"tem_reembolso": True, "reembolso_limitado": False,
                       "tem_penalidade_inadimplemento": False},
        "participacao": {"tem_participacao": False},
    }


def _has(paras: list[str], needle: str) -> bool:
    return any(needle in p for p in paras)


def _escopo(hon: str, *, mensalidade_subtipo="por_processo", mensalidade_variacao="sem_variacao",
            tipo="consultoria_lgpd") -> dict:
    """Escopo válido para um dado tipo de honorário, com o objeto de detalhe exigido."""
    e: dict = {"tipo": tipo, "honorarios": [hon]}
    if hon == "hora_trabalhada":
        e["hora_trabalhada"] = {
            "valor_hora": 300, "tem_teto_mensal": False, "tem_pacote_horas": False,
            "tem_hora_urgencia": False, "tem_hora_fora_expediente": False,
        }
    elif hon == "pro_labore":
        e["pro_labore"] = {"valor_total": 10000, "tem_parcelamento": False}
    elif hon == "mensalidade":
        m = {"valor": 2000, "subtipo": mensalidade_subtipo, "dia_vencimento": "10",
             "variacao_preco": mensalidade_variacao}
        if mensalidade_variacao == "reducao_volume":
            m["faixas_preco"] = [{"faixa": "1-10", "valor": "2000"}, {"faixa": "11+", "valor": "1500"}]
        e["mensalidade"] = m
    elif hon == "exito":
        e["exito"] = {
            "subtipo": "percentual_fixo", "percentual": 20, "incidencia": "beneficio_economico",
            "base_calculo": "x", "vencimento": "a_vista", "forma_pagamento": "x",
            "tem_beneficio_prospectivo": False, "deduz_outro_honorario": False,
        }
    elif hon == "permuta":
        e["permuta"] = {"objeto_permuta": "imovel", "descricao": "x", "tem_torna": False}
    return e


def _req_escopos(escopos: list[dict], *, partes_rel=True) -> dict:
    return {
        "contratantes": [{
            "tipo": "PF", "nome": "Fulano", "nacionalidade": "brasileiro",
            "cpf": "00000000000", "profissao": "x", "estado_civil": "Solteiro(a)",
            "endereco": "rua x", "email": "a@a.com",
        }],
        "incluir_partes_relacionadas": partes_rel,
        "escopos": escopos,
        "acessorios": {"tem_reembolso": True, "reembolso_limitado": False,
                       "tem_penalidade_inadimplemento": False},
        "participacao": {"tem_participacao": False},
    }


def _xml_for(req: dict) -> str:
    data = ContratoRequest(**req)
    gen = ContractGenerator()
    _, path = gen.generate(data, contract_id="FIDELIDADE_XML")
    return zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")


# Casos: cada tipo de honorário, variantes de mensalidade, e combinações.
import pytest
import xml.dom.minidom as _minidom

_CASOS = {
    "hora": [_escopo("hora_trabalhada")],
    "pro_labore": [_escopo("pro_labore")],
    "mensalidade_processo": [_escopo("mensalidade", mensalidade_subtipo="por_processo")],
    "mensalidade_pasta": [_escopo("mensalidade", mensalidade_subtipo="por_pasta")],
    "mensalidade_partido": [_escopo("mensalidade", mensalidade_subtipo="advocacia_partido")],
    "mensalidade_faixas": [_escopo("mensalidade", mensalidade_subtipo="advocacia_partido",
                                   mensalidade_variacao="reducao_volume")],
    "exito": [_escopo("exito")],
    "permuta": [_escopo("permuta")],
    "multi_hora_exito": [_escopo("hora_trabalhada"), _escopo("exito", tipo="consultoria_contratual")],
    "multi_todos": [
        _escopo("hora_trabalhada"),
        _escopo("pro_labore", tipo="consultoria_contratual"),
        _escopo("mensalidade", tipo="consultoria_compliance_trabalhista"),
        _escopo("exito", tipo="contencioso_representacao"),
        _escopo("permuta", tipo="consultoria_opiniao_legal"),
    ],
}


@pytest.mark.parametrize("nome", list(_CASOS.keys()))
def test_secoes_4a11_presentes_para_cada_caso(nome):
    """Cada combinação de honorário/escopo gera todas as seções 4-11 e termina certo."""
    paras = _paras_for(_req_escopos(_CASOS[nome]))
    # Seções comuns sempre presentes (independem do honorário)
    assert _has(paras, "reforma tributária")                 # 4.7
    assert _has(paras, "CredLocaliza")                       # 5.3
    assert _has(paras, "obrigação de meio")                  # 6.3
    assert _has(paras, "inteligência artificial")            # 7.3
    assert _has(paras, "art. 112, §1º, do Código de Processo Civil")  # 8.2.1
    assert _has(paras, "utilizar seu nome, marca e logotipo")  # 9.4
    assert _has(paras, "título executivo extrajudicial")     # 10.7
    assert _has(paras, "por mais privilegiado que seja")     # 11.1
    assert _has(paras, "TESTEMUNHAS:")                       # termina nas assinaturas


@pytest.mark.parametrize("nome", list(_CASOS.keys()))
def test_xml_bem_formado_para_cada_caso(nome):
    """O .docx gerado é XML bem-formado para toda combinação."""
    xml = _xml_for(_req_escopos(_CASOS[nome]))
    _minidom.parseString(xml)  # levanta se malformado


@pytest.mark.parametrize("nome", ["exito", "multi_hora_exito", "multi_todos"])
def test_tabela_exito_presente_quando_ha_exito(nome):
    paras = _paras_for(_req_escopos(_CASOS[nome]))
    assert _has(paras, "50% do percentual de êxito pactuado")


@pytest.mark.parametrize("nome", ["hora", "pro_labore", "mensalidade_processo", "permuta"])
def test_tabela_exito_ausente_quando_nao_ha_exito(nome):
    paras = _paras_for(_req_escopos(_CASOS[nome]))
    assert not _has(paras, "50% do percentual de êxito pactuado")


@pytest.mark.parametrize("partes_rel", [True, False])
def test_solidariedade_condicional_multi_escopo(partes_rel):
    # hora trabalhada presente => com_parte_relacionada segue incluir_partes_relacionadas
    paras = _paras_for(_req_escopos(_CASOS["multi_todos"], partes_rel=partes_rel))
    tem = _has(paras, "assim como no caso de prestação de serviço a Partes Relacionadas")
    assert tem == partes_rel


def test_secao4_reforma_tributaria_e_fraude_completa():
    paras = _paras_for(_base_req())
    assert _has(paras, "canais oficiais de contato do C&F")
    assert _has(paras, "reforma tributária")
    assert _has(paras, "equilíbrio econômico-financeiro")
    assert _has(paras, "forma de faturamento mais eficiente do ponto de vista fiscal")


def test_secao4_solidariedade_com_parte_relacionada():
    paras = _paras_for(_base_req(partes_rel=True))
    assert _has(paras, "assim como no caso de prestação de serviço a Partes Relacionadas")


def test_secao4_solidariedade_sem_parte_relacionada():
    paras = _paras_for(_base_req(partes_rel=False))
    assert _has(paras, "haverá solidariedade entre elas.")
    assert not _has(paras, "assim como no caso de prestação de serviço a Partes Relacionadas")


def test_secao5_reembolsos_completos():
    paras = _paras_for(_base_req())
    assert _has(paras, "CredLocaliza")
    assert _has(paras, "R$ 1,70")
    assert _has(paras, "R$ 0,40")
    assert _has(paras, "honorários sucumbenciais fixados pertencem exclusivamente ao C&F")
    assert _has(paras, "multas processuais e/ou honorários de sucumbência")


def test_secao5_sem_reembolso_omite_51():
    req = _base_req()
    req["acessorios"]["tem_reembolso"] = False
    paras = _paras_for(req)
    assert not _has(paras, "no prazo de até 05 dias")
    assert _has(paras, "CredLocaliza")


def test_secao6_obrigacoes_incisos_completos():
    paras = _paras_for(_base_req())
    assert _has(paras, "autorizar despesas quando exigido")
    assert _has(paras, "cooperar com o C&F na estratégia definida")
    assert _has(paras, "obrigação de meio")


def test_secao7_integridade_lgpd_e_ia():
    paras = _paras_for(_base_req())
    assert _has(paras, "tratar dados pessoais")
    assert _has(paras, "cadastros internos")
    assert _has(paras, "inteligência artificial")
    assert _has(paras, "diretrizes de Governança")


def _req_com_exito() -> dict:
    return _base_req(honorario="exito", extra_escopo={"exito": {
        "subtipo": "percentual_fixo", "percentual": 20, "incidencia": "beneficio_economico",
        "base_calculo": "x", "vencimento": "a_vista", "forma_pagamento": "x",
        "tem_beneficio_prospectivo": False, "deduz_outro_honorario": False,
    }})


def test_secao8_rescisao_cpc_e_extincao():
    paras = _paras_for(_base_req())
    assert _has(paras, "art. 112, §1º, do Código de Processo Civil")
    assert _has(paras, "honorários vencidos serão devidos integralmente")


def test_secao8_tabela_exito_presente_com_exito():
    paras = _paras_for(_req_com_exito())
    assert _has(paras, "50% do percentual de êxito pactuado")
    assert _has(paras, "100% do percentual de êxito pactuado")
    assert _has(paras, "Antes da primeira decisão de mérito")
    assert _has(paras, "inocorrência de determinada fase processual")


def test_secao8_tabela_exito_ausente_sem_exito():
    paras = _paras_for(_base_req(honorario="hora_trabalhada"))
    assert not _has(paras, "50% do percentual de êxito pactuado")


def test_secao9_pi_uso_de_nome_marca():
    paras = _paras_for(_base_req())
    assert _has(paras, "vedada a disponibilização a terceiros")
    assert _has(paras, "utilizar seu nome, marca e logotipo")


def test_secao10_disposicoes_gerais_completas():
    paras = _paras_for(_base_req())
    assert _has(paras, "título executivo extrajudicial")
    assert _has(paras, "MP 2200-2")
    assert _has(paras, "deverá prevalecer em caso de dúvida")


def test_secao11_foro_com_renuncia():
    paras = _paras_for(_base_req())
    assert _has(paras, "com renúncia de qualquer outro, por mais privilegiado que seja")


def test_documento_termina_em_assinaturas():
    paras = _paras_for(_base_req())
    assert _has(paras, "TESTEMUNHAS:")


# ── Feedback 06/07: campos configuráveis e cláusulas ajustadas ──────────────


def test_acessorios_valor_km_configuravel():
    req = _base_req()
    req["acessorios"]["valor_km"] = 2.40
    paras = _paras_for(req)
    assert _has(paras, "R$ 2,40 (dois reais e quarenta centavos)")
    assert not _has(paras, "R$ 1,70")


def test_valor_km_padrao_singular_correto():
    paras = _paras_for(_base_req())
    assert _has(paras, "R$ 1,70 (um real e setenta centavos)")


def test_criterio_extincao_exito_substitui_tabela_de_fases():
    req = _req_com_exito()
    req["acessorios"]["criterio_extincao_exito"] = "assinatura do acordo"
    paras = _paras_for(req)
    assert _has(paras, "observando-se o seguinte critério: assinatura do acordo.")
    assert not _has(paras, "50% do percentual de êxito pactuado")
    assert not _has(paras, "inocorrência de determinada fase processual")
    assert _has(paras, "8.4. Exceto se expressa")


def test_clausulas_adicionais_numeradas_antes_do_foro():
    req = _base_req()
    req["acessorios"]["clausulas_adicionais"] = "Primeira extra.\nSegunda extra."
    paras = _paras_for(req)
    assert _has(paras, "DISPOSIÇÕES ADICIONAIS")
    assert _has(paras, "11.1. Primeira extra.")
    assert _has(paras, "11.2. Segunda extra.")
    assert _has(paras, "12.1. Fica eleito o foro")


def test_exito_incidencia_fundida_com_beneficio():
    paras = _paras_for(_req_com_exito())
    assert _has(paras, "incidirá sobre o benefício econômico, corrigido")
    # As antigas 3.5 ("Incidência:") e 3.6 não existem mais separadas
    assert not _has(paras, "Incidência: benefício econômico.")


def test_exito_forma_pagamento_texto_livre():
    req = _req_com_exito()
    req["escopos"][0]["exito"]["forma_pagamento"] = "quando da formalização do acordo"
    paras = _paras_for(req)
    assert _has(paras, "Forma de pagamento: quando da formalização do acordo.")


def test_exito_sem_forma_pagamento_omite_clausula():
    req = _req_com_exito()
    req["escopos"][0]["exito"]["forma_pagamento"] = ""
    paras = _paras_for(req)
    assert not _has(paras, "Forma de pagamento:")


def test_sem_exito_omite_item_v_da_extincao():
    paras = _paras_for(_base_req())
    assert not _has(paras, "(v) honorários de êxito")


def test_linhas_de_tabela_nao_quebram_entre_paginas():
    xml = _xml_for(_req_escopos(_CASOS["exito"]))
    assert "cantSplit" in xml
    assert "keepNext" in xml
