"""Pedidos do escritorio de nov/2026: CPF das testemunhas, quem falta assinar logo apos o
envio, incidencia do exito (valor recebido / economizado / ambos / customizado) e
exclusao de minuta em rascunho."""
import asyncio
import re
import uuid
import zipfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import (
    AuditLogDB,
    ColaboradorDB,
    ContractDB,
    ContractVersionDB,
    ParticipacaoDB,
    SessionLocal,
    TestemunhaDB,
    utcnow,
)
from app.main import app
from app.models.contract import ContratoRequest
from app.services.arquivo_contrato import resolve_backend_path
from app.services.assinatura import EnvioInvalido, enviar
from app.services.contract_generator import ContractGenerator

CPF = "529.982.247-25"  # ficticio, com digitos verificadores validos
SOCIO = {"email": "socia-nov@cf.com", "name": "Socia", "role": "Contratado"}
CLIENTE = {"email": "cli-nov@ex.com", "name": "Cliente", "role": "Contratante"}


# ── Testemunhas: CPF obrigatorio e impresso sob a assinatura ─────────────────


@pytest.fixture
def db():
    s = SessionLocal()
    s.add(ColaboradorDB(nome="Socia", email=SOCIO["email"], papel="socio", ativo=True))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def contrato(db):
    cid = str(uuid.uuid4())
    out = resolve_backend_path(settings.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    arquivo = out / f"contrato_{cid}.docx"
    arquivo.write_bytes(b"x")
    db.add(ContractDB(contract_id=cid, status="rascunho", client_name="Cliente SA", client_email="c@ex.com",
                      created_by="dona@cf.com", current_version=1, created_at=utcnow(), updated_at=utcnow()))
    db.add(ContractVersionDB(contract_id=cid, version_number=1, form_data_json="{}",
                             file_path=str(arquivo), created_at=utcnow()))
    db.commit()
    yield cid
    arquivo.unlink(missing_ok=True)


def _docuseal(submitters=None):
    d = MagicMock()
    d.create_template_from_docx = AsyncMock(return_value={"id": 1})
    d.send_for_signature = AsyncMock(return_value={
        "success": True, "message": "ok", "submission": {"id": 77, "submitters": submitters or []},
    })
    d.archive_submission = AsyncMock(return_value=True)
    return d


def _enviar(db, cid, signatarios, docuseal):
    return asyncio.run(enviar(db, cid, [dict(s) for s in signatarios], "adv@cf.com", docuseal=docuseal))


def _enviados(d):
    return d.send_for_signature.await_args.kwargs["signatarios"]


def test_testemunha_avulsa_sem_cpf_trava_o_envio(db, contrato):
    """Testemunha digitada na hora, sem CPF (ou com CPF invalido): nada vai ao DocuSeal."""
    d = _docuseal()
    avulsa = {"email": "avulsa@ex.com", "name": "Avulsa", "role": "Testemunha"}
    for cpf in (None, "123.456.789-00"):
        with pytest.raises(EnvioInvalido, match="CPF da testemunha Avulsa"):
            _enviar(db, contrato, [CLIENTE, SOCIO, {**avulsa, **({"cpf": cpf} if cpf else {})}], d)
    d.send_for_signature.assert_not_awaited()


def test_testemunha_do_cadastro_usa_o_cpf_do_cadastro(db, contrato):
    """O CPF de quem esta' no cadastro vem do banco, mesmo que a tela mande outro ou nenhum."""
    db.add(TestemunhaDB(nome="Do Cadastro", email="cadastro@ex.com", cpf="52998224725", ativo=True))
    db.commit()
    d = _docuseal()
    _enviar(db, contrato, [CLIENTE, SOCIO,
                           {"email": "Cadastro@ex.com", "name": "Do Cadastro", "role": "Testemunha"}], d)
    do_cadastro = next(s for s in _enviados(d) if s["email"] == "Cadastro@ex.com")
    assert do_cadastro["cpf"] == "52998224725"


def test_testemunha_1_sai_com_o_cpf_fixo_do_ambiente(db, contrato, monkeypatch):
    """A Testemunha 1 (financeiro) leva o CPF de TESTEMUNHA1_CPF, injetada ou vinda da tela."""
    monkeypatch.setattr(settings, "testemunha1_cpf", CPF)
    d = _docuseal()
    _enviar(db, contrato, [CLIENTE, SOCIO], d)
    assert _enviados(d)[-1]["cpf"] == CPF

    d = _docuseal()
    _enviar(db, contrato, [CLIENTE, SOCIO,
                           {"email": settings.testemunha1_email, "name": "X", "role": "Testemunha"}], d)
    assert _enviados(d)[-1]["cpf"] == CPF


def test_testemunha_1_sem_cpf_no_ambiente_nao_trava_o_envio(db, contrato, monkeypatch):
    """Enquanto TESTEMUNHA1_CPF nao estiver configurado, o contrato sai (sem a linha de CPF dela)."""
    monkeypatch.setattr(settings, "testemunha1_cpf", "")
    assert _enviar(db, contrato, [CLIENTE, SOCIO], _docuseal()).success


def test_envio_devolve_todos_os_signatarios_e_nao_so_o_contratante(db, contrato):
    """Logo apos o envio a tela lista quem falta assinar — socio e testemunhas inclusive."""
    submitters = [
        {"role": "Contratante", "email": CLIENTE["email"], "slug": "a"},
        {"role": "Contratado", "email": SOCIO["email"], "slug": "b"},
        {"role": "Testemunha", "email": settings.testemunha1_email, "slug": "c"},
    ]
    r = _enviar(db, contrato, [CLIENTE, SOCIO], _docuseal(submitters))
    assert [s["role"] for s in r.assinantes] == ["Contratante", "Contratado", "Testemunha"]
    assert [s["role"] for s in r.contratantes] == ["Contratante"]


def _texto(path: str) -> list[str]:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    paras = ["".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p)) for p in xml.split("</w:p>")]
    return [p.replace("&amp;", "&").replace("&quot;", '"') for p in paras if p.strip()]


def _req(exito: dict | None = None, acessorios: dict | None = None) -> dict:
    escopo = {"tipo": "consultoria_lgpd", "honorarios": ["pro_labore"],
              "pro_labore": {"valor_total": 1000, "tem_parcelamento": False}}
    if exito is not None:
        escopo = {"tipo": "consultoria_lgpd", "honorarios": ["exito"], "exito": {
            "subtipo": "percentual_fixo", "percentual": 20, "base_calculo": "", "vencimento": "",
            "forma_pagamento": "", "tem_beneficio_prospectivo": False, "deduz_outro_honorario": False,
            **exito,
        }}
    return {
        "contratantes": [{
            "tipo": "PF", "nome": "Fulano", "nacionalidade": "brasileiro", "cpf": "00000000000",
            "profissao": "x", "estado_civil": "Solteiro(a)", "endereco": "rua x", "email": "a@a.com",
        }],
        "escopos": [escopo],
        "acessorios": {"tem_reembolso": True, "tem_penalidade_inadimplemento": False, **(acessorios or {})},
        "participacao": {"tem_participacao": False},
    }


def _paras(req: dict, roles=None) -> list[str]:
    _, path = ContractGenerator().generate(ContratoRequest(**req), contract_id="NOV2026", signatario_roles=roles)
    return _texto(path)


def _tem(paras: list[str], trecho: str) -> bool:
    return any(trecho in p for p in paras)


def test_cpf_da_testemunha_sai_sob_a_assinatura_so_de_quem_tem():
    paras = _paras(_req(), roles=[
        {"email": "c@a.com", "name": "Client", "role": "Contratante"},
        {"email": "l@cf.com", "name": "Lilian", "role": "Testemunha 1", "cpf": "52998224725"},
        {"email": "o@cf.com", "name": "Outra", "role": "Testemunha 2", "cpf": ""},
    ])
    i = paras.index("TESTEMUNHA 1: LILIAN")
    assert paras[i + 1] == f"CPF: {CPF}"
    assert paras.count(f"CPF: {CPF}") == 1 and "CPF:" not in paras  # a Testemunha 2 fica sem a linha


# ── Exito: incidencia ────────────────────────────────────────────────────────

_POS = ("Os honorários de êxito serão pagos em 3 (três) parcelas mensais, iguais e sucessivas, vencendo-se a "
        "primeira em 10 (dez) dias após a obtenção, ainda que parcial, do Benefício, e as demais no mesmo dia "
        "dos meses subsequentes.")


@pytest.mark.parametrize("incidencia,clausula", [
    ("valor_recebido",
     'Os honorários de êxito corresponderão a 20% (vinte por cento) de qualquer valor recebido pela '
     'CONTRATANTE ("Benefício"), ainda que parcial. Para os fins deste Contrato, considera-se “Benefício” '
     'qualquer valor recebido no âmbito do Objeto ou Escopo contratado, inclusive por decisão, acordo, '
     'compensação ou outra forma de satisfação da pretensão da CONTRATANTE.'),
    ("valor_economizado",
     'Os honorários de êxito corresponderão a 20% (vinte por cento) do Benefício proporcionado à '
     'CONTRATANTE ("Benefício"), ainda que parcial. Para os fins deste Contrato, considera-se “Benefício” '
     'qualquer valor economizado ou cuja exigibilidade seja afastada ou reduzida no âmbito do Objeto ou '
     'Escopo contratado, inclusive por decisão, acordo, compensação ou outra forma de redução da exposição '
     'da CONTRATANTE.'),
    ("ambos",
     'Os honorários de êxito corresponderão a 20% (vinte por cento) do Benefício proporcionado à '
     'CONTRATANTE ("Benefício"), ainda que parcial. Para os fins deste Contrato, considera-se “Benefício” '
     'qualquer valor recebido, economizado ou cuja exigibilidade seja afastada ou reduzida no âmbito do '
     'Objeto ou Escopo contratado, inclusive por decisão, acordo, compensação ou outra forma de satisfação '
     'da pretensão ou de redução da exposição da CONTRATANTE.'),
])
def test_exito_clausulas_modelo_por_incidencia(incidencia, clausula):
    """As duas clausulas-modelo do escritorio, palavra por palavra, para cada incidencia."""
    paras = _paras(_req({"incidencia": incidencia, "forma_pagamento": "parcelado",
                         "numero_parcelas": 3, "vencimento_dias": 10}))
    assert clausula in paras
    assert _POS in paras


def test_exito_customizado_usa_o_conceito_digitado():
    paras = _paras(_req({"incidencia": "customizado",
                         "incidencia_customizada": "o valor do acordo homologado."}))
    assert ('Os honorários de êxito corresponderão a 20% (vinte por cento) do Benefício proporcionado à '
            'CONTRATANTE ("Benefício"), ainda que parcial. Para os fins deste Contrato, considera-se '
            '“Benefício” o valor do acordo homologado.') in paras


def test_exito_a_vista_conta_o_prazo_da_obtencao_do_beneficio():
    paras = _paras(_req({"incidencia": "ambos", "forma_pagamento": "a_vista", "vencimento_dias": 10}))
    assert ("Os honorários de êxito serão pagos à vista, em 10 (dez) dias após a obtenção, ainda que "
            "parcial, do Benefício.") in paras


def test_exito_incidencia_antiga_mantem_a_redacao_antiga():
    """Contrato salvo antes da mudanca nao muda de texto ao ser regerado para assinatura."""
    paras = _paras(_req({"incidencia": "beneficio_economico"}))
    assert _tem(paras, "corresponderão a 20% (vinte por cento) sobre o benefício econômico, corrigido monetariamente")


# ── Extincao ─────────────────────────────────────────────────────────────────


def test_extincao_com_criterio_proprio_usa_a_mesma_abertura_do_item_v():
    paras = _paras(_req({"incidencia": "ambos"}, {"criterio_extincao_exito": "assinatura do acordo"}))
    assert _tem(paras, "e (v) especificamente quanto aos honorários de êxito vincendos ao momento da extinção "
                       "contratual, estes continuarão devidos ao C&F observando-se o seguinte critério: "
                       "assinatura do acordo.")


# ── Excluir minuta em rascunho ───────────────────────────────────────────────


@pytest.fixture
def como_dona():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="d", email="dona@cf.com", name="Dona", role="advogado")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _contagem(db, cid):
    db.expire_all()
    return tuple(db.query(m).filter_by(contract_id=cid).count()
                 for m in (ContractDB, ContractVersionDB, AuditLogDB, ParticipacaoDB))


def test_excluir_minuta_em_rascunho_apaga_tudo_dela(client, db, contrato, como_dona):
    from datetime import date

    db.add(AuditLogDB(contract_id=contrato, action="criacao", created_at=utcnow()))
    db.add(ParticipacaoDB(contract_id=contrato, beneficiario_email="x@cf.com", tipo_honorario="exito",
                          data_inicio=date(2026, 1, 1), aprovada=False))
    db.commit()
    assert _contagem(db, contrato) == (1, 1, 1, 1)

    assert client.delete(f"/api/contracts/{contrato}").status_code == 200
    assert _contagem(db, contrato) == (0, 0, 0, 0)
    assert client.get(f"/api/contracts/{contrato}").status_code == 404


@pytest.mark.parametrize("status", ["enviado", "assinado", "cancelado"])
def test_so_rascunho_pode_ser_excluido(client, db, contrato, como_dona, status):
    db.query(ContractDB).filter_by(contract_id=contrato).update({"status": status})
    db.commit()
    assert client.delete(f"/api/contracts/{contrato}").status_code == 409
    assert _contagem(db, contrato)[:2] == (1, 1)


def test_minuta_que_ja_foi_ao_docuseal_ou_tem_participacao_aprovada_nao_e_excluida(client, db, contrato, como_dona):
    """Voltou a rascunho depois de enviada, ou o financeiro ja' aprovou a ficha: so' cancelar."""
    from datetime import date

    v = db.query(ContractVersionDB).filter_by(contract_id=contrato).one()
    v.docuseal_submission_id = "55"
    db.commit()
    assert client.delete(f"/api/contracts/{contrato}").status_code == 409

    v.docuseal_submission_id = None
    db.add(ParticipacaoDB(contract_id=contrato, beneficiario_email="x@cf.com", tipo_honorario="exito",
                          data_inicio=date(2026, 1, 1), aprovada=True))
    db.commit()
    assert client.delete(f"/api/contracts/{contrato}").status_code == 409
    assert _contagem(db, contrato) == (1, 1, 0, 1)


def test_minuta_de_outra_pessoa_nao_e_excluida(client, db, contrato):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        azure_id="o", email="outra@cf.com", name="Outra", role="advogado")
    try:
        assert client.delete(f"/api/contracts/{contrato}").status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert _contagem(db, contrato)[:2] == (1, 1)


def test_exito_so_com_prazo_e_variavel_ficam_legiveis():
    """Sem forma de pagamento sai so' o prazo; no percentual variavel a frase aponta a tabela."""
    paras = _paras(_req({"incidencia": "valor_economizado", "subtipo": "percentual_variavel",
                         "faixas_percentual": [{"faixa": "Até R$ 1 mi", "percentual": "20"}],
                         "vencimento_dias": 15}))
    assert ("Os honorários de êxito serão pagos em 15 (quinze) dias após a obtenção, ainda que parcial, "
            "do Benefício.") in paras
    assert _tem(paras, "corresponderão ao percentual indicado na tabela abaixo, conforme a faixa de valor, "
                       'do Benefício proporcionado à CONTRATANTE ("Benefício"), ainda que parcial.')


def test_exito_redacao_nova_nao_descarta_os_campos_livres():
    """Parcelamento em texto livre e vencimento antigo continuam saindo na redacao nova."""
    paras = _paras(_req({"incidencia": "ambos", "forma_pagamento": "a_vista",
                         "forma_parcelamento": "entrada e saldo em 60 dias", "vencimento": "no ato do acordo"}))
    assert _tem(paras, "serão pagos à vista, observado o seguinte parcelamento: entrada e saldo em 60 dias, "
                       "com vencimento no ato do acordo.")


def test_cpf_da_testemunha_sai_tambem_no_contrato_de_consumidor(tmp_path):
    from app.models.contrato_consumidor import ContratoConsumidorRequest
    from app.services.consumidor_generator import ConsumidorGenerator
    from tests.test_consumidor_generator import UM

    gen = ConsumidorGenerator()
    gen.output_dir = tmp_path
    paras = _texto(gen.generate(ContratoConsumidorRequest(**UM), signatario_roles=[
        {"email": "m@x.com", "name": "Maria", "role": "Contratante"},
        {"email": "c@x.com", "name": "C&F", "role": "Contratado"},
        {"email": "l@x.com", "name": "Lilian", "role": "Testemunha", "cpf": "52998224725"},
    ])[1])
    assert paras[paras.index("TESTEMUNHA: LILIAN") + 1] == f"CPF: {CPF}"
