"""Previa HTML (services/previa_contrato): sem arquivo no disco e sem depender de router."""
from app.models.contract import ContratoRequest
from app.services.contract_generator import ContractGenerator
from app.services.previa_contrato import docx_para_html, html_do_documento, previa_com_itens

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


def test_previa_do_documento_em_memoria_nao_deixa_arquivo(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    gen = ContractGenerator()
    data = ContratoRequest(**FORM)

    html = html_do_documento(gen._build_document(data))
    com_itens = previa_com_itens(data, gen)

    assert "SERVIÇOS ADVOCATÍCIOS" in html
    assert "SERVIÇOS ADVOCATÍCIOS" in com_itens["preview_html"] and com_itens["itens"]
    assert list(tmp_path.iterdir()) == []  # nada de .docx temporario


def test_docx_para_html_aceita_caminho_e_arquivo_em_memoria(tmp_path):
    gen = ContractGenerator()
    doc = gen._build_document(ContratoRequest(**FORM))
    caminho = tmp_path / "c.docx"
    doc.save(str(caminho))
    assert docx_para_html(caminho) == html_do_documento(doc)
