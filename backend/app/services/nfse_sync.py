"""Orquestrador: recebe XMLs, parseia, persiste, casa, gera pagamento."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.nfse_matcher import MatchStatus, match_nfse
from app.services.nfse_pagamento import gerar_pagamento_para_nfse
from app.models.nfse import CancelamentoData
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


def _contratos_candidatos(db: Session, tomador_doc: str) -> list:
    rows = db.execute(
        text("""
            SELECT c.contract_id, c.cliente_docs,
                   MIN(p.data_inicio) AS data_inicio,
                   MAX(CASE WHEN p.vinculo_ativo THEN NULL ELSE p.data_fim_vinculo END) AS data_fim
            FROM contracts c
            LEFT JOIN participacoes p ON p.contract_id = c.contract_id
            WHERE c.cliente_docs LIKE :pat
            GROUP BY c.contract_id, c.cliente_docs
        """),
        {"pat": f'%"{tomador_doc}"%'},
    ).fetchall()

    class _C:
        def __init__(self, cid, docs_json, data_inicio, data_fim):
            self.contract_id = cid
            self.cliente_docs = json.loads(docs_json or "[]")
            self.data_inicio = data_inicio if isinstance(data_inicio, date) else (
                date.fromisoformat(data_inicio) if data_inicio else date(2024, 8, 1)
            )
            self.data_fim = data_fim if (isinstance(data_fim, date) or data_fim is None) else (
                date.fromisoformat(data_fim) if data_fim else None
            )

    return [_C(*row) for row in rows]


def _participacao_ativa_do_contrato(db: Session, contract_id: str) -> int | None:
    row = db.execute(
        text("""
            SELECT id FROM participacoes
            WHERE contract_id = :c AND vinculo_ativo = TRUE AND aprovada = TRUE
            ORDER BY data_inicio DESC LIMIT 1
        """),
        {"c": contract_id},
    ).fetchone()
    return row[0] if row else None


def _last_insert_id(db: Session) -> int:
    return (
        db.execute(text("SELECT last_insert_rowid()")).scalar()
        if db.bind.dialect.name == "sqlite"
        else db.execute(text("SELECT lastval()")).scalar()
    )


def _create_job(db: Session, cnpj: str, origem: str, disparado_por: str | None, ini: date, fim: date) -> int:
    now = datetime.now(timezone.utc)
    db.execute(
        text("""
            INSERT INTO sync_jobs (cnpj_prestador, origem, disparado_por,
                                   iniciado_em, periodo_inicio, periodo_fim, status)
            VALUES (:c, :o, :u, :n, :i, :f, 'em_andamento')
        """),
        {"c": cnpj, "o": origem, "u": disparado_por, "n": now, "i": ini, "f": fim},
    )
    db.commit()
    return _last_insert_id(db)


def _finalize_job(db: Session, job_id: int, outcome: JobOutcome) -> None:
    db.execute(
        text("""
            UPDATE sync_jobs
            SET finalizado_em = :n, total_nfs = :t, auto_vinculadas = :a,
                pendentes = :p, sem_match = :s, erros = :e,
                status = :st, motivo_falha = :mf, ultimo_nsu = :nsu
            WHERE id = :id
        """),
        {
            "n": datetime.now(timezone.utc),
            "t": outcome.total_nfs,
            "a": outcome.auto_vinculadas,
            "p": outcome.pendentes,
            "s": outcome.sem_match,
            "e": outcome.erros,
            "st": outcome.status,
            "mf": outcome.motivo_falha,
            "nsu": outcome.ultimo_nsu,
            "id": job_id,
        },
    )
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
    em_andamento = db.execute(
        text("""
            SELECT id FROM sync_jobs
            WHERE cnpj_prestador = :c AND status = 'em_andamento'
            ORDER BY iniciado_em DESC LIMIT 1
        """),
        {"c": cnpj_prestador},
    ).fetchone()
    if em_andamento:
        raise JobLockError(f"sync_job {em_andamento[0]} ainda em andamento")

    job_id = _create_job(db, cnpj_prestador, origem, disparado_por, periodo_inicio, periodo_fim)
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
                atualizou = db.execute(
                    text("""
                        UPDATE nfse_recebidas
                        SET cancelada = TRUE, data_cancelamento = :d,
                            status_matching = 'cancelada',
                            atualizado_em = :n, motivo = 'cancelada pelo prestador'
                        WHERE chave_acesso = :ch AND cancelada = FALSE
                    """),
                    {"d": nf.data_cancelamento, "n": datetime.now(timezone.utc), "ch": nf.chave_acesso},
                ).rowcount
                db.commit()
                total += atualizou
                continue

            if nf.chave_acesso:
                # Padrao nacional: a chave identifica a nota. Nao usa numero/serie,
                # que podem repetir numeros antigos do BHISS para o mesmo CNPJ.
                existing = db.execute(
                    text("SELECT id, cancelada FROM nfse_recebidas WHERE chave_acesso = :ch"),
                    {"ch": nf.chave_acesso},
                ).fetchone()
            else:
                existing = db.execute(
                    text("""
                        SELECT id, cancelada FROM nfse_recebidas
                        WHERE cnpj_prestador = :c AND numero = :n
                          AND (serie = :s OR (serie IS NULL AND :s IS NULL)) AND direcao = :d
                    """),
                    {"c": nf.cnpj_prestador, "n": nf.numero, "s": nf.serie, "d": nf.direcao},
                ).fetchone()

            if existing:
                nfse_id, was_cancelada = existing
                if nf.cancelada and not was_cancelada:
                    db.execute(
                        text("""
                            UPDATE nfse_recebidas
                            SET cancelada = TRUE, data_cancelamento = :d,
                                status_matching = 'cancelada',
                                atualizado_em = :n, motivo = 'cancelada pelo prestador'
                            WHERE id = :i
                        """),
                        {"d": nf.data_cancelamento, "n": datetime.now(timezone.utc), "i": nfse_id},
                    )
                    db.commit()
                    total += 1
                continue

            candidatos = [] if nf.direcao == "recebida" else _contratos_candidatos(db, nf.tomador_doc)
            match = match_nfse(nf, candidatos)

            contract_id = match.contract_id
            participacao_id = _participacao_ativa_do_contrato(db, contract_id) if contract_id else None

            status = "cancelada" if nf.cancelada else match.status.value
            if nf.cancelada:
                pass
            elif match.status == MatchStatus.AUTO:
                auto += 1
            elif match.status == MatchStatus.PENDENTE:
                pend += 1
            elif match.status == MatchStatus.SEM_MATCH:
                sem += 1

            db.execute(
                text("""
                    INSERT INTO nfse_recebidas (
                        cnpj_prestador, numero, serie, codigo_verificacao,
                        competencia, data_emissao, tomador_doc, tomador_nome,
                        valor_servicos, iss_retido, irrf, pis, cofins, csll,
                        valor_liquido, discriminacao, cancelada, data_cancelamento,
                        xml_raw, contract_id, participacao_id, status_matching, motivo,
                        direcao, chave_acesso
                    ) VALUES (
                        :cnpj, :num, :ser, :cv,
                        :cmp, :em, :td, :tn,
                        :vs, :iss, :ir, :pis, :co, :cs,
                        :vl, :dis, :canc, :dc,
                        :xml, :cid, :pid, :st, :mot,
                        :dir, :ch
                    )
                """),
                {
                    "cnpj": nf.cnpj_prestador,
                    "num": nf.numero,
                    "ser": nf.serie,
                    "cv": nf.codigo_verificacao,
                    "cmp": nf.competencia,
                    "em": nf.data_emissao,
                    "td": nf.tomador_doc,
                    "tn": nf.tomador_nome,
                    "vs": float(nf.valor_servicos),
                    "iss": float(nf.iss_retido),
                    "ir": float(nf.irrf),
                    "pis": float(nf.pis),
                    "co": float(nf.cofins),
                    "cs": float(nf.csll),
                    "vl": float(nf.valor_liquido),
                    "dis": nf.discriminacao,
                    "canc": nf.cancelada,
                    "dc": nf.data_cancelamento,
                    "xml": nf.xml_raw,
                    "cid": contract_id,
                    "pid": participacao_id,
                    "st": status,
                    "mot": match.motivo,
                    "dir": nf.direcao,
                    "ch": nf.chave_acesso,
                },
            )
            db.commit()
            total += 1

            if not nf.cancelada and match.status == MatchStatus.AUTO and participacao_id:
                new_id = db.execute(text("SELECT id FROM nfse_recebidas ORDER BY id DESC LIMIT 1")).scalar()
                gerar_pagamento_para_nfse(db, nfse_id=new_id)
    except Exception as e:
        # Sem isso o job ficava em 'em_andamento' e todo ingest seguinte do
        # CNPJ dava 409 (JobLockError) ate alguem corrigir o banco a mao.
        db.rollback()
        _finalize_job(db, job_id, JobOutcome(
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
    _finalize_job(db, job_id, outcome)
    return outcome
