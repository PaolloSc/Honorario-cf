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
