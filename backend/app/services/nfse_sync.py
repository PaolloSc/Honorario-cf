"""Orquestrador: recebe XMLs, parseia, persiste, casa, gera pagamento."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.nfse import CancelamentoData
from app.models.nfse_db import SyncJobDB
from app.services import notas_recebidas as notas
from app.services.nfse_matcher import MatchStatus, match_nfse
from app.services.nfse_pagamento import gerar_pagamento_para_nfse
from app.services.nfse_parser import NFSeParseError, parse_documento


@dataclass
class JobOutcome:
    status: str
    total_nfs: int
    auto_vinculadas: int
    pendentes: int
    sem_match: int
    erros: int
    motivo_falha: str | None = None
    ultimo_nsu: int | None = None


class JobLockError(Exception):
    """Outro sync ainda em andamento para o mesmo CNPJ."""


def _finalize_job(db: Session, job: SyncJobDB, outcome: JobOutcome) -> None:
    job.finalizado_em = datetime.now(timezone.utc)
    job.total_nfs = outcome.total_nfs
    job.auto_vinculadas = outcome.auto_vinculadas
    job.pendentes = outcome.pendentes
    job.sem_match = outcome.sem_match
    job.erros = outcome.erros
    job.status = outcome.status
    job.motivo_falha = outcome.motivo_falha
    job.ultimo_nsu = outcome.ultimo_nsu
    db.commit()


def ingest_payload(
    db: Session,
    *,
    cnpj_prestador: str,
    periodo_inicio: date,
    periodo_fim: date,
    origem: str,
    disparado_por: str | None,
    xmls: Iterable[bytes],
    ultimo_nsu: int | None = None,
) -> JobOutcome:
    em_andamento = notas.job_em_andamento(db, cnpj_prestador)
    if em_andamento:
        raise JobLockError(f"sync_job {em_andamento.id} ainda em andamento")

    job = notas.criar_job(db, cnpj_prestador, origem, disparado_por, periodo_inicio, periodo_fim)
    total = auto = pend = sem = errs = 0

    try:
        for xml in xmls:
            try:
                nf = parse_documento(xml, cnpj_prestador)
            except NFSeParseError:
                errs += 1
                continue
            if nf is None:  # evento do ADN que nao altera a nota
                continue
            if isinstance(nf, CancelamentoData):
                # ponytail: evento cuja nota ainda nao foi ingerida nao tem efeito;
                # na ordem do NSU a nota sempre chega antes do seu evento.
                atualizou = notas.cancelar_por_chave(db, nf.chave_acesso, nf.data_cancelamento)
                db.commit()
                total += atualizou
                continue

            existing = notas.achar_existente(db, nf)
            if existing:
                if nf.cancelada and not existing.cancelada:
                    notas.marcar_cancelada(db, existing, nf.data_cancelamento)
                    db.commit()
                    total += 1
                continue

            candidatos = [] if nf.direcao == "recebida" else notas.contratos_candidatos(db, nf.tomador_doc)
            match = match_nfse(nf, candidatos)

            contract_id = match.contract_id
            participacao_id = notas.participacao_ativa_do_contrato(db, contract_id) if contract_id else None

            status = "cancelada" if nf.cancelada else match.status.value
            if nf.cancelada:
                pass
            elif match.status == MatchStatus.AUTO:
                auto += 1
            elif match.status == MatchStatus.PENDENTE:
                pend += 1
            elif match.status == MatchStatus.SEM_MATCH:
                sem += 1

            nota = notas.criar_nota(
                db, nf, contract_id=contract_id, participacao_id=participacao_id,
                status=status, motivo=match.motivo,
            )
            db.commit()
            total += 1

            if not nf.cancelada and match.status == MatchStatus.AUTO and participacao_id:
                gerar_pagamento_para_nfse(db, nfse_id=nota.id)
    except Exception as e:
        # Sem isso o job ficava em 'em_andamento' e todo ingest seguinte do
        # CNPJ dava 409 (JobLockError) ate alguem corrigir o banco a mao.
        db.rollback()
        _finalize_job(db, job, JobOutcome(
            status="erro", total_nfs=total, auto_vinculadas=auto, pendentes=pend,
            sem_match=sem, erros=errs + 1, motivo_falha=f"{type(e).__name__}: {e}"[:500],
        ))
        raise

    outcome = JobOutcome(
        status="ok",
        total_nfs=total,
        auto_vinculadas=auto,
        pendentes=pend,
        sem_match=sem,
        erros=errs,
        ultimo_nsu=ultimo_nsu,
    )
    _finalize_job(db, job, outcome)
    return outcome
