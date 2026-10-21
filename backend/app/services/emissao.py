"""Emissao de NFS-e: fatura aprovada -> DPS assinada -> SEFIN Nacional (PRODUCAO RESTRITA) -> nota.

Regras que mordem (architecture.md, secao 7):
- uma nota viva por fatura (indice parcial do banco) e idempotencia por chave: duplo clique,
  timeout e repeticao nao geram duas notas;
- a nota nasce em 'processando' e e GRAVADA ANTES da chamada de rede, com a DPS assinada;
- sem resposta (timeout, 5xx sem erro estruturado) NUNCA reenvia: fica 'processando' e a
  consulta pela DPS (GET /dps/{id}) decide;
- o certificado so e decifrado em memoria; eventos e erros nao levam segredo nem a DPS;
- o ambiente aceito aqui e so 'homologacao' (producao restrita): producao nao esta implementada.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from lxml import etree
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.emissao_db import (
    ContratoFaturamentoDB, EmissorConfigDB, FaturaDB, NfseEmitidaDB, NfseEmitidaEventoDB,
    ServicoDB, TomadorDB, proximo_dps,
)
from app.config import settings
from app.services.crypto import InvalidCipherError
from app.services.emissor_cert import cnpjs_do_certificado, decifrar_certificado, tem_certificado
from workers.nfse_adn.cert import CertificadoError, carregar_pfx, ssl_context_do_pfx
from workers.nfse_dps_smoke.assinatura import assinar_dps
from workers.nfse_dps_smoke.dps import DpsParams, id_dps, montar_dps, regras_locais
from workers.nfse_dps_smoke.sefin import (
    Resposta, get_dps, get_nfse, post_dps, uma_linha, xml_da_nota,
)

IDADE_MIN_PARA_CONCLUIR_S = 300  # antes disso "nao achei a nota" ainda pode ser so demora


class EmissaoErro(Exception):
    """Falha de regra de negocio, com o status HTTP que a rota deve devolver."""

    def __init__(self, status_code: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status_code = status_code
        self.mensagem = mensagem


def _brt() -> datetime:
    return datetime.now(ZoneInfo("America/Sao_Paulo"))


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


# --- configuracao e cliente mTLS -------------------------------------------------

def _cfg_pronto(db: Session) -> EmissorConfigDB:
    cfg = db.get(EmissorConfigDB, 1)
    if cfg is None or not cfg.ativo:
        raise EmissaoErro(409, "Emissor nao configurado ou inativo: configure e ative em Emissor")
    if not tem_certificado(cfg):
        raise EmissaoErro(409, "Emissor sem certificado")
    if cfg.ambiente != "homologacao":
        # A flag e rechecada a CADA emissao (nao so ao salvar a configuracao). E, mesmo ligada, a DPS e
        # o host so existem para producao restrita nesta etapa.
        if not settings.nfse_emissao_producao_permitida:
            raise EmissaoErro(409, "Emissao em producao nao esta habilitada (NFSE_EMISSAO_PRODUCAO_PERMITIDA desligada)")
        raise EmissaoErro(409, "Emissao em producao nao esta implementada: use o ambiente 'homologacao'")
    return cfg


def _certificado(cfg: EmissorConfigDB, cnpj: str | None = None):
    """(key, cert, ctx_tls) abertos so em memoria. `cnpj`: o prestador da nota (padrao: o do emissor)."""
    try:
        pfx, senha = decifrar_certificado(cfg)
        key, cert, _ = carregar_pfx(pfx, senha)
        ctx = ssl_context_do_pfx(pfx, senha)
    except (CertificadoError, InvalidCipherError, ValueError, RuntimeError):
        raise EmissaoErro(409, "Certificado do emissor ilegivel: envie o certificado de novo") from None
    if (cnpj or cfg.cnpj) not in cnpjs_do_certificado(cert):  # confere de novo na hora de usar, de forma exata
        raise EmissaoErro(409, "O certificado guardado nao e do CNPJ do emissor" if cnpj is None
                          else "O certificado vigente nao e do prestador desta nota: so ele pode consultar a DPS")
    return key, cert, ctx


# --- eventos --------------------------------------------------------------------

def _evento(db: Session, nota: NfseEmitidaDB, tipo: str, payload: dict) -> None:
    db.add(NfseEmitidaEventoDB(nfse_emitida_id=nota.id, tipo=tipo, payload=payload))


def _payload_resposta(r: Resposta) -> dict:
    return {
        "http": r.status, "base": r.base, "chave": r.chave,
        "erros": [{"codigo": c[:20], "mensagem": uma_linha(m)[:500]} for c, m in r.erros],
        **({} if r.erros or r.sucesso else {"texto": uma_linha(r.texto)[:300]}),
    }


# --- montagem -------------------------------------------------------------------

def _snapshot_tomador(t: TomadorDB) -> dict:
    return {
        "documento": t.documento, "nome": t.nome, "emails": list(t.emails or []),
        "inscricao_municipal": t.inscricao_municipal, "optante_simples": bool(t.optante_simples),
        "orgao_publico": bool(t.orgao_publico), "cep": t.cep, "logradouro": t.logradouro, "numero": t.numero,
        "complemento": t.complemento, "bairro": t.bairro, "municipio_ibge": t.municipio_ibge, "uf": t.uf,
    }


def _snapshot_servico(s: ServicoDB, cfg: EmissorConfigDB) -> dict:
    return {
        "nome": s.nome, "descricao_padrao": s.descricao_padrao, "c_trib_nac": s.c_trib_nac, "c_trib_mun": s.c_trib_mun,
        "nbs": s.nbs, "aliquota_iss": str(s.aliquota_iss) if s.aliquota_iss is not None else None,
        "iss_retido": bool(s.iss_retido_padrao), "incluir_ibscbs": bool(s.incluir_ibscbs), "c_ind_op": s.c_ind_op,
        "cst_ibscbs": s.cst_ibscbs, "c_class_trib": s.c_class_trib,
        "emissor": {  # regime e IM vigentes na emissao
            "municipio_ibge": cfg.municipio_ibge, "op_simp_nac": cfg.op_simp_nac, "reg_ap_trib_sn": cfg.reg_ap_trib_sn,
            "reg_esp_trib": cfg.reg_esp_trib, "inscricao_municipal": cfg.inscricao_municipal, "serie": cfg.serie_dps,
        },
    }


def _params(f: FaturaDB, tom: dict, srv: dict, cnpj: str, numero: int, agora: datetime | None) -> DpsParams:
    emi = srv["emissor"]
    doc = tom["documento"]
    end = {"cMun": tom["municipio_ibge"], "CEP": tom["cep"], "xLgr": tom["logradouro"], "nro": tom["numero"],
           "xBairro": tom["bairro"], "xCpl": tom["complemento"]}
    return DpsParams(
        cnpj_prestador=cnpj, serie=emi["serie"], n_dps=numero, valor=Decimal(f.valor_bruto),
        c_trib_nac=srv["c_trib_nac"], c_trib_mun=srv["c_trib_mun"], nbs=srv["nbs"], descricao=f.descricao,
        c_mun=emi["municipio_ibge"], op_simp_nac=emi["op_simp_nac"], reg_ap_trib_sn=emi["reg_ap_trib_sn"],
        reg_esp_trib=emi["reg_esp_trib"], im=emi["inscricao_municipal"],
        tp_ret_issqn="2" if srv["iss_retido"] else "1",
        aliquota_iss=Decimal(srv["aliquota_iss"]) if srv["aliquota_iss"] is not None else None,
        tomador_cnpj=doc if len(doc) == 14 else "", tomador_cpf=doc if len(doc) == 11 else None,
        tomador_nome=tom["nome"], tomador_end=end, competencia=f.competencia,
        ibscbs=srv["incluir_ibscbs"], c_ind_op=srv["c_ind_op"] or "100301", cst=srv["cst_ibscbs"] or "000",
        c_class_trib=srv["c_class_trib"] or "000001", ver_aplic="honorario-cf", agora=agora,
    )


# --- aplicar a resposta do SEFIN --------------------------------------------------

def _ler_nota(xml: bytes | None) -> tuple[str | None, Decimal]:
    """(numero da NFS-e, vISSQN) do XML devolvido; tolera XML ausente ou fora do esperado."""
    if not xml:
        return None, Decimal("0")
    try:
        raiz = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
        numero = raiz.findtext(".//{*}nNFSe")
        iss = raiz.findtext(".//{*}vISSQN")
        return (numero or None), Decimal(iss) if iss else Decimal("0")
    except (etree.XMLSyntaxError, ArithmeticError):
        return None, Decimal("0")


def _autorizar(db: Session, nota: NfseEmitidaDB, fatura: FaturaDB, chave: str, xml: bytes | None) -> None:
    numero, iss = _ler_nota(xml)
    nota.status, nota.chave_acesso, nota.numero_nfse = "autorizada", chave, numero
    nota.iss, nota.erro_codigo, nota.erro_mensagem = iss, None, None
    if xml:
        nota.xml_nfse = xml
    nota.emitida_em = nota.emitida_em or _agora_utc()
    fatura.status = "emitida"


def _rejeitar(db: Session, nota: NfseEmitidaDB, fatura: FaturaDB, codigo: str, mensagem: str) -> None:
    nota.status, nota.erro_codigo, nota.erro_mensagem = "rejeitada", codigo[:20], uma_linha(mensagem)[:2000]
    fatura.status = "aprovada"  # corrigir e reenviar gera nova DPS


def _aplicar_resposta(db: Session, nota: NfseEmitidaDB, fatura: FaturaDB, r: Resposta) -> None:
    _evento(db, nota, "resposta", _payload_resposta(r))
    if r.sucesso:
        _autorizar(db, nota, fatura, r.chave, xml_da_nota(r.corpo))
    elif r.erros and 400 <= r.status < 500:
        # So 4xx e rejeicao do SEFIN (libera nova DPS). 5xx com corpo de erro e falha do servidor: o
        # resultado e desconhecido (a nota pode ter sido gerada), entao fica processando e so a consulta decide.
        codigo, mensagem = r.erros[0]
        resto = [f"{c}: {m}" for c, m in r.erros[1:]]
        _rejeitar(db, nota, fatura, codigo, "; ".join([mensagem, *resto]))
    # senao: inconclusivo (5xx, com ou sem erro; pagina de erro): continua processando; a consulta decide


# --- emitir ---------------------------------------------------------------------

def _cliente(ctx) -> httpx.Client:
    # httpx fala HTTP/1.1 por padrao: o SEFIN recusa HTTP/2 (HTTP_1_1_REQUIRED).
    return httpx.Client(verify=ctx, timeout=60)


def _nota_viva(db: Session, fatura_id: int) -> NfseEmitidaDB | None:
    return (db.query(NfseEmitidaDB)
            .filter(NfseEmitidaDB.fatura_id == fatura_id, NfseEmitidaDB.status.in_(("processando", "autorizada")))
            .first())


def emitir(db: Session, fatura_id: int, idempotency_key: str, usuario: str,
           http: httpx.Client | None = None, agora: datetime | None = None) -> NfseEmitidaDB:
    chave_idem = (idempotency_key or "").strip()
    if not chave_idem or len(chave_idem) > 80:
        raise EmissaoErro(400, "Cabecalho Idempotency-Key obrigatorio (ate 80 caracteres)")

    # 1) repeticao da mesma intencao: devolve o que ja existe (consultando antes, se ainda processando)
    previa = db.query(NfseEmitidaDB).filter(NfseEmitidaDB.idempotency_key == chave_idem).first()
    if previa is not None:
        if previa.fatura_id != fatura_id:
            raise EmissaoErro(409, "Idempotency-Key ja usada em outra fatura")
        return consultar(db, previa.id, http=http, agora=agora) if previa.status == "processando" else previa

    fatura = db.get(FaturaDB, fatura_id)
    if fatura is None:
        raise EmissaoErro(404, "Fatura nao encontrada")

    # 2) ja ha nota viva para a fatura (outra chave): nao cria outra
    viva = _nota_viva(db, fatura_id)
    if viva is not None:
        return consultar(db, viva.id, http=http, agora=agora) if viva.status == "processando" else viva

    if fatura.status != "aprovada":
        dica = " Aprove a fatura antes." if fatura.status == "rascunho" else ""
        raise EmissaoErro(409, f"Fatura {fatura.status}: so fatura aprovada pode ser emitida.{dica}")
    cf = db.get(ContratoFaturamentoDB, fatura.contract_id)
    if cf is None or cf.origem != "honorario":
        raise EmissaoErro(409, "Este contrato e faturado pelo Legal One: mude para 'honorario' antes de emitir")
    cfg = _cfg_pronto(db)
    tomador, servico = db.get(TomadorDB, fatura.tomador_id), db.get(ServicoDB, fatura.servico_id)
    if not tomador.ativo or not servico.ativo:
        raise EmissaoErro(409, "Tomador ou servico inativo")
    if fatura.competencia > _brt().date():
        raise EmissaoErro(400, "Competencia no futuro: a competencia nao pode passar da data de emissao")

    tom, srv = _snapshot_tomador(tomador), _snapshot_servico(servico, cfg)
    # valida as regras do Anexo I antes de gastar um numero de DPS
    params = _params(fatura, tom, srv, cfg.cnpj, 1, agora)
    erros = regras_locais(params)
    # cIndOp 100301 (demais servicos onerosos, Anexo C): incidencia no domicilio do adquirente => E0239 sem endereco
    if params.ibscbs and not all((params.tomador_end or {}).get(k) for k in ("cMun", "CEP", "xLgr", "nro", "xBairro")):
        erros.append("E0239: com IBS/CBS o tomador precisa de endereco nacional completo "
                     "(CEP, logradouro, numero, bairro e municipio): complete o cadastro do tomador")
    if erros:
        raise EmissaoErro(400, "A DPS seria rejeitada: " + "; ".join(erros))
    key, cert, ctx = _certificado(cfg)

    # 3) grava a nota ANTES da rede: numero, DPS assinada, fatura 'emitindo'
    try:
        numero = proximo_dps(db, cfg.cnpj, cfg.serie_dps, cfg.ambiente)
        params = _params(fatura, tom, srv, cfg.cnpj, numero, agora)
        assinado = assinar_dps(montar_dps(params), key, cert)
        nota = NfseEmitidaDB(
            fatura_id=fatura.id, status="processando", ambiente=cfg.ambiente, cnpj_prestador=cfg.cnpj,
            dps_serie=cfg.serie_dps, dps_numero=numero, idempotency_key=chave_idem,
            valor_servicos=fatura.valor_bruto, retencoes={"iss_retido": srv["iss_retido"]},
            tomador_snapshot=tom, servico_snapshot=srv, xml_dps=assinado, emitida_por=usuario,
        )
        db.add(nota)
        fatura.status = "emitindo"
        db.flush()
        _evento(db, nota, "enviada", {"id_dps": id_dps(cfg.municipio_ibge, cfg.cnpj, cfg.serie_dps, numero),
                                      "serie": cfg.serie_dps, "numero": numero})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmissaoErro(409, "Ja ha uma emissao em andamento para esta fatura") from None

    # 4) envia. Qualquer falha daqui em diante deixa 'processando': nunca reenvia as cegas.
    proprio = http is None
    http = http or _cliente(ctx)
    try:
        r = post_dps(http, assinado)
    except httpx.HTTPError as e:
        _evento(db, nota, "erro", {"tipo": type(e).__name__})
        db.commit()
        return nota
    finally:
        if proprio:
            http.close()
    _aplicar_resposta(db, nota, fatura, r)
    db.commit()
    return nota


# --- consultar ------------------------------------------------------------------

def consultar(db: Session, nota_id: int, http: httpx.Client | None = None, agora: datetime | None = None,
              idade_min_s: int = IDADE_MIN_PARA_CONCLUIR_S, confirmar_sem_nota: bool = False) -> NfseEmitidaDB:
    """Descobre pela DPS o que aconteceu com uma nota 'processando' (ou busca o XML de uma autorizada
    sem XML). So le do SEFIN: nao envia DPS.

    Nao depende do emissor estar ativo: uma nota em aberto precisa poder ser consultada mesmo depois
    de desativar o emissor. Usa o certificado vigente, que tem de ser do prestador da nota.
    'Nao achei a nota' (SEM_NOTA) libera nova DPS: sozinho, depois de `idade_min_s`, so em
    homologacao; em producao so com `confirmar_sem_nota` (decisao de uma pessoa)."""
    nota = db.get(NfseEmitidaDB, nota_id)
    if nota is None:
        raise EmissaoErro(404, "Nota nao encontrada")
    if nota.status not in ("processando", "autorizada") or (nota.status == "autorizada" and nota.xml_nfse):
        return nota
    cfg = db.get(EmissorConfigDB, 1)
    if cfg is None or not tem_certificado(cfg):
        raise EmissaoErro(409, "Emissor sem certificado: nao ha como consultar o SEFIN")
    fatura = db.get(FaturaDB, nota.fatura_id)
    _, _, ctx = _certificado(cfg, nota.cnpj_prestador)
    municipio = ((nota.servico_snapshot or {}).get("emissor") or {}).get("municipio_ibge") or cfg.municipio_ibge

    proprio = http is None
    http = http or _cliente(ctx)
    try:
        chave = nota.chave_acesso
        if nota.status == "processando":
            r = get_dps(http, id_dps(municipio, nota.cnpj_prestador, nota.dps_serie, nota.dps_numero))
            _evento(db, nota, "consulta", _payload_resposta(r))
            chave = r.chave if r.status == 200 else None
            if chave is None:
                idade = (agora or _agora_utc()) - _aware(nota.criado_em)
                automatico = nota.ambiente == "homologacao" and idade >= timedelta(seconds=idade_min_s)
                if r.status == 404 and (automatico or confirmar_sem_nota):
                    _rejeitar(db, nota, fatura, "SEM_NOTA", "A consulta pela DPS nao encontrou NFS-e gerada")
                db.commit()
                return nota
        r2 = get_nfse(http, chave)
        _evento(db, nota, "consulta", _payload_resposta(r2))
        _autorizar(db, nota, fatura, chave, xml_da_nota(r2.corpo) if r2.status == 200 else None)
        db.commit()
    except httpx.HTTPError as e:
        _evento(db, nota, "erro", {"tipo": type(e).__name__})
        db.commit()
    finally:
        if proprio:
            http.close()
    return nota


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
