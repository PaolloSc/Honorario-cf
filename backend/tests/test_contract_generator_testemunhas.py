"""Testemunhas digitais no DOCX gerado (campos DocuSeal vs bloco fisico)."""
import re
import zipfile

from app.models.contract import ContratoRequest
from app.services.contract_generator import ContractGenerator


def _text_of(path: str) -> str:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    paras = []
    for p in re.split(r"</w:p>", xml):
        txt = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p))
        if txt.strip():
            paras.append(txt)
    return "\n".join(paras)


def _req() -> dict:
    return {
        "contratantes": [{
            "tipo": "PF", "nome": "Fulano", "nacionalidade": "brasileiro",
            "cpf": "00000000000", "profissao": "x", "estado_civil": "Solteiro(a)",
            "endereco": "rua x", "email": "a@a.com",
        }],
        "escopos": [{"tipo": "consultoria_lgpd", "honorarios": ["pro_labore"],
                     "pro_labore": {"valor_total": 1000, "tem_parcelamento": False}}],
        "acessorios": {"tem_reembolso": True, "tem_penalidade_inadimplemento": False},
        "participacao": {"tem_participacao": False},
    }


def test_digital_testemunha_fields_rendered():
    data = ContratoRequest(**_req())
    roles = [
        {"email": "c@a.com", "name": "Client", "role": "Contratante"},
        {"email": "lilian@cf.com", "name": "Lilian Silveira Correa", "role": "Testemunha 1"},
        {"email": "outra@cf.com", "name": "Outra Pessoa", "role": "Testemunha 2"},
    ]
    gen = ContractGenerator()
    _, path = gen.generate(data, contract_id="TESTEM_DIGITAL", signatario_roles=roles)
    text = _text_of(path)

    assert "type=signature;role=Testemunha 1" in text
    assert "type=signature;role=Testemunha 2" in text
    # Sem bloco fisico em branco (sem linhas de CPF de testemunha)
    assert "CPF:" not in text


def test_initial_generation_keeps_physical_block():
    """Sem signatario_roles -> mantem bloco fisico em branco (compat)."""
    data = ContratoRequest(**_req())
    gen = ContractGenerator()
    _, path = gen.generate(data, contract_id="TESTEM_FISICO")
    text = _text_of(path)

    assert "TESTEMUNHAS:" in text
    assert "CPF:" in text
    assert "role=Testemunha" not in text


def test_socio_que_tambem_e_advogado_tem_um_bloco_contratado_so():
    """Sócio assina como advogado e pelo escritório: o bloco CONTRATADO sai uma vez (merge duplicou o laço)."""
    data = ContratoRequest(**_req())
    roles = [
        {"email": "c@a.com", "name": "Client", "role": "Contratante"},
        {"email": "monica@cf.com", "name": "Monica Socia", "role": "Advogado",
         "also_contratado": True, "contratado_nome": "Carvalho & Furtado Advogados"},
    ]
    _, path = ContractGenerator().generate(data, contract_id="CONTRATADO_UNICO", signatario_roles=roles)
    # A qualificacao das partes tambem comeca com "CONTRATADO:"; so' a linha exata e' assinatura.
    blocos = [l for l in _text_of(path).splitlines() if l == "CONTRATADO: CARVALHO &amp; FURTADO ADVOGADOS"]
    assert len(blocos) == 1
