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
