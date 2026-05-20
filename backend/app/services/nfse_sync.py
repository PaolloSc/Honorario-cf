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
from app.services.nfse_parser import NFSeParseError, parse_nfse_xml


@dataclass
class JobOutcome:
    status: str
    total_nfs: int
    auto_vinculadas: int
    pendentes: int
    sem_match: int
    erros: int
    motivo_falha: str | None = None


def _contratos_candidatos(db: Session, tomador_doc: str) -> list:
    rows = db.execute(
        text("""
            SELECT c.contract_id, c.cliente_docs,
                   MIN(p.data_inicio) AS data_inicio,
                   MAX(CASE WHEN p.vinculo_ativo=1 THEN NULL ELSE p.data_fim_vinculo END) AS data_fim
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
            WHERE contract_id = :c AND vinculo_ativo = 1 AND aprovada = 1
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
                status = :st, motivo_falha = :mf
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
) -> JobOutcome:
    job_id = _create_job(db, cnpj_prestador, origem, disparado_por, periodo_inicio, periodo_fim)
    total = auto = pend = sem = errs = 0

    for xml in xmls:
        try:
            nf = parse_nfse_xml(xml)
        except NFSeParseError:
            errs += 1
            continue

        existing = db.execute(
            text("""
                SELECT id, cancelada FROM nfse_recebidas
                WHERE cnpj_prestador = :c AND numero = :n
                  AND (serie IS :s OR serie = :s)
            """),
            {"c": nf.cnpj_prestador, "n": nf.numero, "s": nf.serie},
        ).fetchone()

        if existing:
            nfse_id, was_cancelada = existing
            if nf.cancelada and not was_cancelada:
                db.execute(
                    text("""
                        UPDATE nfse_recebidas
                        SET cancelada = 1, data_cancelamento = :d,
                            status_matching = 'cancelada',
                            atualizado_em = :n, motivo = 'cancelada pelo prestador'
                        WHERE id = :i
                    """),
                    {"d": nf.data_cancelamento, "n": datetime.now(timezone.utc), "i": nfse_id},
                )
                db.commit()
                total += 1
            continue

        candidatos = _contratos_candidatos(db, nf.tomador_doc)
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
        else:
            sem += 1

        db.execute(
            text("""
                INSERT INTO nfse_recebidas (
                    cnpj_prestador, numero, serie, codigo_verificacao,
                    competencia, data_emissao, tomador_doc, tomador_nome,
                    valor_servicos, iss_retido, irrf, pis, cofins, csll,
                    valor_liquido, discriminacao, cancelada, data_cancelamento,
                    xml_raw, contract_id, participacao_id, status_matching, motivo
                ) VALUES (
                    :cnpj, :num, :ser, :cv,
                    :cmp, :em, :td, :tn,
                    :vs, :iss, :ir, :pis, :co, :cs,
                    :vl, :dis, :canc, :dc,
                    :xml, :cid, :pid, :st, :mot
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
                "canc": 1 if nf.cancelada else 0,
                "dc": nf.data_cancelamento,
                "xml": nf.xml_raw,
                "cid": contract_id,
                "pid": participacao_id,
                "st": status,
                "mot": match.motivo,
            },
        )
        db.commit()
        total += 1

        if not nf.cancelada and match.status == MatchStatus.AUTO and participacao_id:
            new_id = db.execute(text("SELECT id FROM nfse_recebidas ORDER BY id DESC LIMIT 1")).scalar()
            gerar_pagamento_para_nfse(db, nfse_id=new_id)

    outcome = JobOutcome(
        status="ok",
        total_nfs=total,
        auto_vinculadas=auto,
        pendentes=pend,
        sem_match=sem,
        erros=errs,
    )
    _finalize_job(db, job_id, outcome)
    return outcome
