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


def _padrao(id_, **extra) -> str:
    return _por_id(_build(**extra)[1].itens)[id_]["padrao"]


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
    assert item["status"] == "padrao_mudou" and not item["ajustado"]
    assert item["ajuste"] == "Meu texto."  # guardado para reaplicar
    # nao aplica no DOCX: usa o padrao atual
    assert "Meu texto." not in _texto_docx(doc)
    assert item["padrao"] in _texto_docx(doc)
    assert ctx.descartados() == []


def _req_exito_mensalidade(**extra) -> dict:
    r = _req(**extra)
    r["escopos"] = [{
        "tipo": "consultoria_lgpd", "honorarios": ["mensalidade", "exito"],
        "mensalidade": {"subtipo": "por_pasta", "valor": 500, "dia_vencimento": "10"},
        "exito": {"percentual": 10},
    }]
    return r


def _build_em(**extra):
    doc = ContractGenerator()._build_document(ContratoRequest(**_req_exito_mensalidade(**extra)))
    return doc, doc._cf_itens


def test_ids_de_honorario_sao_semanticos():
    _, ctx = _build_em()
    ids = [i["id"] for i in ctx.itens if i["clausula"].startswith("OUTRAS DISPOSIÇÕES")]
    assert any(i.startswith("hon.mensalidade.") for i in ids) and any(i.startswith("hon.exito.") for i in ids)


def test_desligar_exito_nao_muda_o_ajuste_da_mensalidade():
    _, base = _build_em()
    m = next(i for i in base.itens if i["id"] == "hon.mensalidade.2")
    ajuste = {"hon.mensalidade.2": {"texto": "Mensalidade reescrita.", "padrao": m["padrao"]}}
    doc, ctx = _build_em(ajustes_texto=ajuste)
    assert "Mensalidade reescrita." in _texto_docx(doc)
    # desliga o exito: o item da mensalidade segue com o mesmo id e o mesmo texto padrao
    sem_exito = _req_exito_mensalidade(ajustes_texto=ajuste)
    sem_exito["escopos"][0]["honorarios"] = ["mensalidade"]
    sem_exito["escopos"][0].pop("exito")
    d2 = ContractGenerator()._build_document(ContratoRequest(**sem_exito))
    item = _por_id(d2._cf_itens.itens)["hon.mensalidade.2"]
    assert item["ajustado"] and item["status"] == "ok"
    assert "Mensalidade reescrita." in _texto_docx(d2)
    assert not any(i["id"].startswith("hon.exito") for i in d2._cf_itens.itens)


def test_mudar_valor_deixa_ajuste_pendente_e_docx_com_padrao():
    _, base = _build_em()
    m = next(i for i in base.itens if i["id"].startswith("hon.mensalidade.") and "500" in i["padrao"])
    ajuste = {m["id"]: {"texto": "Mensalidade reescrita.", "padrao": m["padrao"]}}
    r = _req_exito_mensalidade(ajustes_texto=ajuste)
    r["escopos"][0]["mensalidade"]["valor"] = 900
    doc = ContractGenerator()._build_document(ContratoRequest(**r))
    item = _por_id(doc._cf_itens.itens)[m["id"]]
    assert item["status"] == "padrao_mudou" and not item["ajustado"]
    assert "Mensalidade reescrita." not in _texto_docx(doc)
    assert item["padrao"] in _texto_docx(doc)


def test_clausula_adicional_tem_id_pelo_conteudo_e_aceita_ajuste():
    ac = {"tem_reembolso": True, "tem_penalidade_inadimplemento": False,
          "clausulas_adicionais": "Clausula livre um.\nClausula livre dois."}
    _, base = _build(acessorios=ac)
    extras = [i for i in base.itens if i["clausula"] == "DISPOSIÇÕES ADICIONAIS"]
    assert all(i["id"].startswith("adic.") for i in extras)
    dois = next(i for i in extras if i["padrao"] == "Clausula livre dois.")
    # apagar a primeira nao muda o id da segunda
    ac2 = {**ac, "clausulas_adicionais": "Clausula livre dois."}
    doc, ctx = _build(
        acessorios=ac2,
        ajustes_texto={dois["id"]: {"texto": "Dois ajustada.", "padrao": dois["padrao"]}},
    )
    assert "Dois ajustada." in _texto_docx(doc)


def test_generate_grava_docx_com_ajuste(tmp_path):
    data = ContratoRequest(**_req(ajustes_texto={"2.2": {"texto": "Ajustado no arquivo.", "padrao": _padrao("2.2")}}))
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
            ajustes_texto={"2.2": {"texto": "Texto marcado.", "padrao": _padrao("2.2")}, "88.1": {"texto": "x", "padrao": ""}}
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

    form = json.loads(json.dumps(_req(ajustes_texto={"2.2": {"texto": "Ajuste salvo.", "padrao": _padrao("2.2")}})))
    contrato, gen = parse_form_data(form)
    doc = gen._build_document(contrato)
    assert "Ajuste salvo." in _texto_docx(doc)
