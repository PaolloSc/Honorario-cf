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
    assert itens["escopo.objeto"]["clausula"] == "OBJETO, ESCOPO E HONORÁRIO"
    assert all(not i["ajustado"] for i in ctx.itens)
    assert len(itens) == len(ctx.itens)  # ids unicos


def test_ajuste_aplicado_no_docx():
    _, base = _build()
    alvo = _por_id(base.itens)["escopo.nao_incluidos_escopo"]
    doc, ctx = _build(ajustes_texto={"escopo.nao_incluidos_escopo": {"texto": "Texto\nnovo   da  clausula.", "padrao": alvo["padrao"]}})
    item = _por_id(ctx.itens)["escopo.nao_incluidos_escopo"]
    assert item["ajustado"] and item["status"] == "ok"
    assert item["texto"] == "Texto novo da clausula."
    assert "Texto novo da clausula." in _texto_docx(doc)
    assert alvo["padrao"] not in _texto_docx(doc)
    assert ctx.descartados() == []


def test_marcador_do_docuseal_no_ajuste_e_removido():
    _, base = _build()
    alvo = _por_id(base.itens)["escopo.nao_incluidos_escopo"]
    doc, ctx = _build(ajustes_texto={"escopo.nao_incluidos_escopo": {
        "texto": "Antes {{Assinatura;type=signature;role=Contratante}} depois {{x", "padrao": alvo["padrao"]}})
    texto = _texto_docx(doc)
    assert "{{" not in texto and "}}" not in texto
    assert _por_id(ctx.itens)["escopo.nao_incluidos_escopo"]["ajustado"]
    assert "Antes Assinatura;type=signature;role=Contratante depois x" in texto


def test_revisao_da_ia_le_so_os_ajustes_aplicados():
    from app.services import contract_reviewer

    _, base = _build()
    itens = _por_id(base.itens)
    ok, mudou = "escopo.nao_incluidos_escopo", "escopo.objeto"
    ajustes = {
        ok: {"texto": "Texto aplicado.", "padrao": itens[ok]["padrao"]},
        mudou: {"texto": "Texto com padrao velho.", "padrao": "padrao antigo"},
        "99.9": {"texto": "Texto descartado.", "padrao": "x"},
    }
    data = _req(ajustes_texto=ajustes)
    _, ctx = _build(ajustes_texto=ajustes)
    aplicados = {i["id"] for i in ctx.itens if i["ajustado"]}
    assert aplicados == {ok}
    texto = contract_reviewer.extract_open_fields(data, aplicados)
    assert "Texto aplicado." in texto
    assert "padrao velho" not in texto and "descartado" not in texto


def test_item_inexistente_e_ignorado():
    doc, ctx = _build(ajustes_texto={"99.9": {"texto": "fantasma", "padrao": "x"}})
    assert "fantasma" not in _texto_docx(doc)
    assert [d["id"] for d in ctx.descartados()] == ["99.9"]


def test_texto_padrao_mudou_avisa_mas_mantem_ajuste():
    doc, ctx = _build(ajustes_texto={"escopo.nao_incluidos_escopo": {"texto": "Meu texto.", "padrao": "padrao antigo"}})
    item = _por_id(ctx.itens)["escopo.nao_incluidos_escopo"]
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
    assert "hon.mensalidade.pagamento_processo" in ids and "hon.exito.incidencia" in ids


def test_desligar_exito_nao_muda_o_ajuste_da_mensalidade():
    _, base = _build_em()
    m = next(i for i in base.itens if i["id"] == "hon.mensalidade.ativo")
    ajuste = {"hon.mensalidade.ativo": {"texto": "Mensalidade reescrita.", "padrao": m["padrao"]}}
    doc, ctx = _build_em(ajustes_texto=ajuste)
    assert "Mensalidade reescrita." in _texto_docx(doc)
    # desliga o exito: o item da mensalidade segue com o mesmo id e o mesmo texto padrao
    sem_exito = _req_exito_mensalidade(ajustes_texto=ajuste)
    sem_exito["escopos"][0]["honorarios"] = ["mensalidade"]
    sem_exito["escopos"][0].pop("exito")
    d2 = ContractGenerator()._build_document(ContratoRequest(**sem_exito))
    item = _por_id(d2._cf_itens.itens)["hon.mensalidade.ativo"]
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
    data = ContratoRequest(**_req(ajustes_texto={"escopo.nao_incluidos_escopo": {"texto": "Ajustado no arquivo.", "padrao": _padrao("escopo.nao_incluidos_escopo")}}))
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
            ajustes_texto={"escopo.nao_incluidos_escopo": {"texto": "Texto marcado.", "padrao": _padrao("escopo.nao_incluidos_escopo")}, "88.1": {"texto": "x", "padrao": ""}}
        ))
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    body = r.json()
    assert r.status_code == 200
    assert '<p class="ajustado">2.2. Texto marcado.</p>' in body["preview_html"]
    assert [d["id"] for d in body["ajustes_descartados"]] == ["88.1"]
    assert {"id", "clausula", "texto", "padrao", "ajustado", "editavel", "etapa"} <= set(body["itens"][0])


def test_ajuste_sobrevive_ao_json_salvo_e_regeracao():
    """DOCX regerado a partir do form_data salvo (assinatura/e-mail) mantem o ajuste."""
    import json

    from app.services.contract_dispatch import parse_form_data

    form = json.loads(json.dumps(_req(ajustes_texto={"escopo.nao_incluidos_escopo": {"texto": "Ajuste salvo.", "padrao": _padrao("escopo.nao_incluidos_escopo")}})))
    contrato, gen = parse_form_data(form)
    doc = gen._build_document(contrato)
    assert "Ajuste salvo." in _texto_docx(doc)


def test_chaves_sem_numero_posicional():
    _, ctx = _build()
    assert all(not re.fullmatch(r"[\d.]+", i["id"]) for i in ctx.itens)
    assert _por_id(ctx.itens)["acess.custas"]["numero"].startswith("5.")


def test_caso_da_angela_desligar_reembolso_nao_move_o_ajuste_de_custas():
    """Ajusta 'Custas' (5.2), desliga o reembolso: 'Custas' vira 5.1 mas o ajuste segue nela,
    e a clausula CredLocaliza nunca recebe o texto de Custas."""
    ac = {"tem_reembolso": True, "tem_penalidade_inadimplemento": False}
    _, base = _build(acessorios=ac)
    custas = _por_id(base.itens)["acess.custas"]
    assert custas["numero"] == "5.2"
    ajuste = {"acess.custas": {"texto": "Custas ajustadas pela advogada.", "padrao": custas["padrao"]}}
    doc, ctx = _build(acessorios={**ac, "tem_reembolso": False}, ajustes_texto=ajuste)
    itens = _por_id(ctx.itens)
    assert itens["acess.custas"]["numero"] == "5.1" and itens["acess.custas"]["ajustado"]
    cred = itens["acess.credlocaliza"]
    assert "CredLocaliza" in cred["texto"] and not cred["ajustado"]
    assert "Custas ajustadas pela advogada." in _texto_docx(doc)
    assert cred["padrao"] in _texto_docx(doc)  # CredLocaliza intacta


def test_ajuste_de_chave_que_sumiu_vai_para_descartados_com_o_texto():
    ac = {"tem_reembolso": True, "tem_penalidade_inadimplemento": False}
    ajuste = {"acess.reembolso": {"texto": "Meu reembolso.", "padrao": _padrao("acess.reembolso", acessorios=ac)}}
    doc, ctx = _build(acessorios={**ac, "tem_reembolso": False}, ajustes_texto=ajuste)
    assert ctx.descartados() == [{"id": "acess.reembolso", "texto": "Meu reembolso."}]
    assert "Meu reembolso." not in _texto_docx(doc)  # nunca aplicado em outra clausula
    assert not any(i["ajustado"] for i in ctx.itens)


def test_clausula_opcional_no_meio_do_bloco_de_honorario_nao_move_as_outras():
    """Desconto/limitacao entrando no meio do bloco nao muda a chave das demais clausulas."""
    def chaves(**ex):
        r = _req_exito_mensalidade()
        r["escopos"][0]["mensalidade"].update(ex)
        d = ContractGenerator()._build_document(ContratoRequest(**r))
        return {i["id"]: i["padrao"] for i in d._cf_itens.itens}
    sem = chaves()
    com = chaves(variacao_preco="limitacao_temporal", limitacao_temporal_anos=3)
    assert "hon.mensalidade.limitacao_temporal" in com and "hon.mensalidade.limitacao_temporal" not in sem
    for k, padrao in sem.items():
        assert com[k] == padrao


def _combos():
    import itertools

    base_ac = {"tem_reembolso": True, "tem_penalidade_inadimplemento": False}
    for reemb, limitado, vig, crit, adic, parte in itertools.product(
        (True, False), (True, False), (True, False), (True, False), (True, False), (True, False)
    ):
        ac = {**base_ac, "tem_reembolso": reemb, "reembolso_limitado": limitado,
              "descricao_limitacao_reembolso": "ate R$ 100" if limitado else None}
        if vig:
            ac["vigencia_inicio"] = "2026-01-01"
        if crit:
            ac["criterio_extincao_exito"] = "formalizacao do acordo"
        if adic:
            ac["clausulas_adicionais"] = "Livre A.\nLivre B."
        yield ac, parte


def _escopos_variados():
    pro = {"tipo": "consultoria_lgpd", "honorarios": ["pro_labore"], "pro_labore": {"valor_total": 1000, "tem_parcelamento": False}}
    mens = {"tipo": "consultoria_lgpd", "honorarios": ["mensalidade"],
            "mensalidade": {"subtipo": "por_pasta", "valor": 500, "dia_vencimento": "10", "desconto_percentual": 5}}
    partido = {"tipo": "consultoria_lgpd", "honorarios": ["mensalidade"],
               "mensalidade": {"subtipo": "advocacia_partido", "valor": 500, "dia_vencimento": "10"}}
    exito = {"tipo": "consultoria_lgpd", "honorarios": ["exito"], "exito": {"percentual": 10}}
    hora = {"tipo": "consultoria_lgpd", "honorarios": ["hora_trabalhada"],
            "hora_trabalhada": {"valor_hora": 300, "tem_hora_urgencia": True, "tem_teto_mensal": True, "valor_teto_mensal": 9000}}
    permuta = {"tipo": "consultoria_lgpd", "honorarios": ["permuta"], "permuta": {"objeto_permuta": "design", "tem_torna": True, "valor_torna": 100}}
    return [[pro], [mens], [partido], [exito], [hora], [permuta], [mens, exito], [hora, mens, exito, pro], [pro, permuta]]


def test_todas_as_combinacoes_chaves_unicas_e_identidade_estavel():
    """Para cada combinacao de opcoes: nenhuma chave repetida, e a mesma chave sempre
    designa a mesma clausula (mesmo inicio de texto), nao importa o que esteja ligado."""
    identidade: dict[str, str] = {}
    combos = list(_combos())
    variados = _escopos_variados()
    # todas as opcoes de acessorios com um honorario simples; todos os honorarios com 2 extremos
    pares = [(ac, parte, variados[6]) for ac, parte in combos] + [
        (ac, parte, esc) for ac, parte in (combos[0], combos[-1]) for esc in variados
    ]
    for ac, parte, escopos in pares:
        r = _req(acessorios=ac, escopos=escopos, incluir_partes_relacionadas=parte)
        doc = ContractGenerator()._build_document(ContratoRequest(**r))
        ctx = doc._cf_itens
        ids = [i["id"] for i in ctx.itens]
        duplicadas = [i for i in ctx.duplicadas if not i.startswith("adic.")]
        assert not duplicadas, duplicadas
        assert len(ids) == len(set(ids))
        for i in ctx.itens:
            if i["id"].startswith("adic."):
                continue
            assert identidade.setdefault(i["id"], i["padrao"][:18]) == i["padrao"][:18], i["id"]
