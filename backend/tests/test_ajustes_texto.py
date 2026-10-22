"""Ajuste manual de clausulas (etapa 7): aplicado, item inexistente ignorado, padrao mudado."""
import re
import zipfile

from app.models.contract import ContratoRequest
from app.services.contract_generator import ContractGenerator


def _req(**extra) -> dict:
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
        **extra,
    }


def _build(**extra):
    doc = ContractGenerator()._build_document(ContratoRequest(**_req(**extra)))
    return doc, doc._cf_itens


def _por_id(itens):
    return {i["id"]: i for i in itens}


def _texto_docx(doc) -> str:
    return "\n".join(p.text for p in doc.paragraphs)


def test_itens_tem_id_estavel_e_texto_padrao():
    _, ctx = _build()
    itens = _por_id(ctx.itens)
    assert itens["2.1"]["clausula"] == "OBJETO, ESCOPO E HONORÁRIO"
    assert all(not i["ajustado"] for i in ctx.itens)
    assert len(itens) == len(ctx.itens)  # ids unicos


def test_ajuste_aplicado_no_docx():
    _, base = _build()
    alvo = _por_id(base.itens)["2.2"]
    doc, ctx = _build(ajustes_texto={"2.2": {"texto": "Texto\nnovo   da  clausula.", "padrao": alvo["padrao"]}})
    item = _por_id(ctx.itens)["2.2"]
    assert item["ajustado"] and item["status"] == "ok"
    assert item["texto"] == "Texto novo da clausula."
    assert "Texto novo da clausula." in _texto_docx(doc)
    assert alvo["padrao"] not in _texto_docx(doc)
    assert ctx.descartados() == []


def test_item_inexistente_e_ignorado():
    doc, ctx = _build(ajustes_texto={"99.9": {"texto": "fantasma", "padrao": "x"}})
    assert "fantasma" not in _texto_docx(doc)
    assert ctx.descartados() == ["99.9"]


def test_texto_padrao_mudou_avisa_mas_mantem_ajuste():
    doc, ctx = _build(ajustes_texto={"2.2": {"texto": "Meu texto.", "padrao": "padrao antigo"}})
    item = _por_id(ctx.itens)["2.2"]
    assert item["status"] == "padrao_mudou"
    assert "Meu texto." in _texto_docx(doc)


def test_secao_de_honorarios_aceita_ajuste_e_avisa_se_o_padrao_mudar():
    _, base = _build()
    fee = next(i for i in base.itens if i["clausula"].startswith("OUTRAS DISPOSIÇÕES"))
    assert fee["editavel"] and fee["etapa"] is None
    doc, ctx = _build(ajustes_texto={fee["id"]: {"texto": "Honorario reescrito.", "padrao": fee["padrao"]}})
    assert "Honorario reescrito." in _texto_docx(doc)
    assert _por_id(ctx.itens)[fee["id"]]["status"] == "ok"
    # valor mudou nas etapas: o texto padrao muda e o ajuste e' mantido com aviso
    _, ctx2 = _build(ajustes_texto={fee["id"]: {"texto": "Honorario reescrito.", "padrao": "R$ 1,00"}})
    assert _por_id(ctx2.itens)[fee["id"]]["status"] == "padrao_mudou"


def test_clausulas_adicionais_aceitam_ajuste():
    doc0, base = _build(acessorios={"tem_reembolso": True, "tem_penalidade_inadimplemento": False,
                                    "clausulas_adicionais": "Clausula livre um."})
    extra = next(i for i in base.itens if i["clausula"] == "DISPOSIÇÕES ADICIONAIS")
    assert extra["editavel"]
    doc, _ = _build(
        acessorios={"tem_reembolso": True, "tem_penalidade_inadimplemento": False, "clausulas_adicionais": "Clausula livre um."},
        ajustes_texto={extra["id"]: {"texto": "Livre ajustada.", "padrao": extra["padrao"]}},
    )
    assert "Livre ajustada." in _texto_docx(doc)


def test_generate_grava_docx_com_ajuste(tmp_path):
    data = ContratoRequest(**_req(ajustes_texto={"2.2": {"texto": "Ajustado no arquivo.", "padrao": ""}}))
    _, path = ContractGenerator().generate(data, contract_id="AJUSTE_DOCX")
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    assert "Ajustado no arquivo." in "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml))


def test_endpoint_previa_marca_item_ajustado(client):
    from app.auth import CurrentUser, get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="x", email="lawyer@test.com", name="Lawyer", role="admin"
    )
    try:
        r = client.post("/api/contract/preview-texto", json=_req(
            ajustes_texto={"2.2": {"texto": "Texto marcado.", "padrao": ""}, "88.1": {"texto": "x", "padrao": ""}}
        ))
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    body = r.json()
    assert r.status_code == 200
    assert '<p class="ajustado">2.2. Texto marcado.</p>' in body["preview_html"]
    assert body["ajustes_descartados"] == ["88.1"]
    assert {"id", "clausula", "texto", "padrao", "ajustado", "editavel", "etapa"} <= set(body["itens"][0])


def test_ajuste_sobrevive_ao_json_salvo_e_regeracao():
    """DOCX regerado a partir do form_data salvo (assinatura/e-mail) mantem o ajuste."""
    import json

    from app.services.contract_dispatch import parse_form_data

    form = json.loads(json.dumps(_req(ajustes_texto={"2.2": {"texto": "Ajuste salvo.", "padrao": ""}})))
    contrato, gen = parse_form_data(form)
    doc = gen._build_document(contrato)
    assert "Ajuste salvo." in _texto_docx(doc)
