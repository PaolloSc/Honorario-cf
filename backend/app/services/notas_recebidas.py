"""Notas fiscais recebidas do ADN/BHISS e os jobs de sincronizacao: um lugar so' para ler e gravar.

Antes, o sync, as rotas e o pagamento falavam com as tabelas por SQL cru, ao lado dos
modelos ORM que ja existiam sem uso. Aqui tudo passa pelo ORM; o orquestrador (nfse_sync)
e as rotas so' decidem o que fazer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session, defer

from app.database import ContractDB, ParticipacaoDB
from app.models.nfse import NFSeData
from app.models.nfse_db import NFSeAuditLogDB, NFSeRecebidaDB, SyncJobDB

DATA_INICIO_PADRAO = date(2024, 8, 1)  # contrato sem participacao registrada: vale desde o corte


def agora() -> datetime:
    return datetime.now(timezone.utc)


class NotaNaoEncontrada(Exception):
    pass


class ContratoNaoExiste(Exception):
    pass


class NotaNaoVinculavel(Exception):
    """A nota ja' esta vinculada automaticamente ou e' de fornecedor."""


# ── Contratos candidatos ao casamento ──────────────────────────────────────


@dataclass
class ContratoCandidato:
    contract_id: str
    cliente_docs: list[str]
    data_inicio: date
    data_fim: date | None


def contratos_candidatos(db: Session, tomador_doc: str) -> list[ContratoCandidato]:
    """Contratos cujo cliente tem este documento, com o periodo em que ha participacao."""
    fim = case((ParticipacaoDB.vinculo_ativo.is_(True), None), else_=ParticipacaoDB.data_fim_vinculo)
    linhas = (
        db.query(
            ContractDB.contract_id,
            ContractDB.cliente_docs,
            func.min(ParticipacaoDB.data_inicio),
            func.max(fim),
        )
        .outerjoin(ParticipacaoDB, ParticipacaoDB.contract_id == ContractDB.contract_id)
        .filter(ContractDB.cliente_docs.like(f'%"{tomador_doc}"%'))
        .group_by(ContractDB.contract_id, ContractDB.cliente_docs)
        .all()
    )
    return [
        ContratoCandidato(
            contract_id=cid,
            cliente_docs=json.loads(docs or "[]"),
            data_inicio=_como_data(inicio) or DATA_INICIO_PADRAO,
            data_fim=_como_data(fim_),
        )
        for cid, docs, inicio, fim_ in linhas
    ]


def _como_data(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def participacao_ativa_do_contrato(db: Session, contract_id: str) -> int | None:
    """A participacao aprovada e ativa mais recente do contrato (a que recebe o pagamento)."""
    p = (
        db.query(ParticipacaoDB.id)
        .filter(
            ParticipacaoDB.contract_id == contract_id,
            ParticipacaoDB.vinculo_ativo.is_(True),
            ParticipacaoDB.aprovada.is_(True),
        )
        .order_by(ParticipacaoDB.data_inicio.desc())
        .first()
    )
    return p[0] if p else None


# ── Notas ──────────────────────────────────────────────────────────────────


def achar_existente(db: Session, nf: NFSeData) -> NFSeRecebidaDB | None:
    """Padrao nacional: a chave identifica a nota (numero/serie podem repetir numeros antigos do
    BHISS para o mesmo CNPJ). Sem chave: CNPJ + numero + serie + direcao."""
    q = db.query(NFSeRecebidaDB).options(defer(NFSeRecebidaDB.xml_raw))
    if nf.chave_acesso:
        return q.filter(NFSeRecebidaDB.chave_acesso == nf.chave_acesso).first()
    return q.filter(
        NFSeRecebidaDB.cnpj_prestador == nf.cnpj_prestador,
        NFSeRecebidaDB.numero == nf.numero,
        NFSeRecebidaDB.serie.is_(None) if nf.serie is None else NFSeRecebidaDB.serie == nf.serie,
        NFSeRecebidaDB.direcao == nf.direcao,
    ).first()


def marcar_cancelada(db: Session, nota: NFSeRecebidaDB, quando: datetime | None) -> None:
    nota.cancelada = True
    nota.data_cancelamento = quando
    nota.status_matching = "cancelada"
    nota.atualizado_em = agora()
    nota.motivo = "cancelada pelo prestador"


def cancelar_por_chave(db: Session, chave: str, quando: datetime | None) -> int:
    """Evento de cancelamento do padrao nacional. Evento cuja nota ainda nao chegou nao tem efeito
    (na ordem do NSU a nota sempre vem antes do seu evento). Devolve quantas notas mudou (0 ou 1)."""
    nota = (
        db.query(NFSeRecebidaDB)
        .options(defer(NFSeRecebidaDB.xml_raw))
        .filter(NFSeRecebidaDB.chave_acesso == chave, NFSeRecebidaDB.cancelada.is_(False))
        .first()
    )
    if nota is None:
        return 0
    marcar_cancelada(db, nota, quando)
    return 1


def criar_nota(
    db: Session, nf: NFSeData, *, contract_id: str | None, participacao_id: int | None, status: str, motivo: str | None
) -> NFSeRecebidaDB:
    nota = NFSeRecebidaDB(
        cnpj_prestador=nf.cnpj_prestador,
        numero=nf.numero,
        serie=nf.serie,
        codigo_verificacao=nf.codigo_verificacao,
        competencia=nf.competencia,
        data_emissao=nf.data_emissao,
        tomador_doc=nf.tomador_doc,
        tomador_nome=nf.tomador_nome,
        valor_servicos=nf.valor_servicos,
        iss_retido=nf.iss_retido,
        irrf=nf.irrf,
        pis=nf.pis,
        cofins=nf.cofins,
        csll=nf.csll,
        valor_liquido=nf.valor_liquido,
        discriminacao=nf.discriminacao,
        cancelada=nf.cancelada,
        data_cancelamento=nf.data_cancelamento,
        xml_raw=nf.xml_raw,
        contract_id=contract_id,
        participacao_id=participacao_id,
        status_matching=status,
        motivo=motivo,
        direcao=nf.direcao,
        chave_acesso=nf.chave_acesso,
    )
    db.add(nota)
    db.flush()  # o id vem da propria insercao (antes: "ultimo id da tabela", que erra com dois syncs)
    return nota


def listar(
    db: Session,
    *,
    direcao: str | None = None,
    cnpj_prestador: str | None = None,
    competencia_de: date | None = None,
    competencia_ate: date | None = None,
    status: str | None = None,
    limite: int = 500,
) -> list[NFSeRecebidaDB]:
    q = db.query(NFSeRecebidaDB).options(defer(NFSeRecebidaDB.xml_raw))
    if direcao:
        q = q.filter(NFSeRecebidaDB.direcao == direcao)
    if cnpj_prestador:
        q = q.filter(NFSeRecebidaDB.cnpj_prestador == cnpj_prestador)
    if competencia_de and competencia_ate:
        q = q.filter(NFSeRecebidaDB.competencia.between(competencia_de, competencia_ate))
    if status:
        q = q.filter(NFSeRecebidaDB.status_matching == status)
    return q.order_by(NFSeRecebidaDB.data_emissao.desc()).limit(limite).all()


def vincular_manual(
    db: Session, nfse_id: int, contract_id: str, motivo: str | None, user_email: str
) -> tuple[NFSeRecebidaDB, int | None]:
    """Vinculo manual da nota a um contrato. Devolve a nota e a participacao que passou a valer
    (None se o contrato nao tem participacao ativa e aprovada). Quem chama gera o pagamento."""
    nota = db.get(NFSeRecebidaDB, nfse_id)
    if nota is None:
        raise NotaNaoEncontrada()
    if nota.status_matching == "auto":
        raise NotaNaoVinculavel("NFS-e ja vinculada automaticamente; use 'revisar'")
    if nota.status_matching == "recebida":
        raise NotaNaoVinculavel("NFS-e recebida de fornecedor nao se vincula a contrato")
    if db.query(ContractDB.contract_id).filter(ContractDB.contract_id == contract_id).first() is None:
        raise ContratoNaoExiste()

    participacao_id = participacao_ativa_do_contrato(db, contract_id)
    agora_ = agora()
    nota.contract_id = contract_id
    nota.participacao_id = participacao_id
    nota.status_matching = "manual"
    nota.motivo = motivo or "vinculo manual"
    nota.atualizado_em = agora_
    db.add(NFSeAuditLogDB(nfse_id=nfse_id, acao="nfse.vincular_manual", user_email=user_email, ts=agora_))
    db.commit()
    return nota, participacao_id


# ── Jobs de sincronizacao ──────────────────────────────────────────────────


def job_em_andamento(db: Session, cnpj: str) -> SyncJobDB | None:
    return (
        db.query(SyncJobDB)
        .filter(SyncJobDB.cnpj_prestador == cnpj, SyncJobDB.status == "em_andamento")
        .order_by(SyncJobDB.iniciado_em.desc())
        .first()
    )


def criar_job(
    db: Session, cnpj: str, origem: str, disparado_por: str | None, inicio: date, fim: date,
    *, status: str = "em_andamento",
) -> SyncJobDB:
    job = SyncJobDB(
        cnpj_prestador=cnpj, origem=origem, disparado_por=disparado_por,
        iniciado_em=agora(), periodo_inicio=inicio, periodo_fim=fim, status=status,
    )
    db.add(job)
    db.commit()
    return job


def registrar_falha_do_worker(db: Session, cnpj: str, status: str, motivo: str | None) -> None:
    """O worker avisa uma falha antes de ingerir (login, captcha, layout). Nao faz commit."""
    quando = agora()
    db.add(SyncJobDB(
        cnpj_prestador=cnpj, origem="cron", iniciado_em=quando, finalizado_em=quando,
        periodo_inicio=quando.date(), periodo_fim=quando.date(), status=status, motivo_falha=motivo,
    ))


def ultimo_job(db: Session, cnpj: str | None = None) -> SyncJobDB | None:
    q = db.query(SyncJobDB)
    if cnpj:
        return q.filter(SyncJobDB.cnpj_prestador == cnpj).order_by(SyncJobDB.id.desc()).first()
    return q.order_by(SyncJobDB.iniciado_em.desc()).first()


def ultimo_nsu(db: Session, cnpj: str) -> int:
    nsu = (
        db.query(func.max(SyncJobDB.ultimo_nsu))
        .filter(SyncJobDB.cnpj_prestador == cnpj, SyncJobDB.status == "ok")
        .scalar()
    )
    return int(nsu or 0)
