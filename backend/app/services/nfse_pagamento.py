"""Cria registro em participacao_pagamentos para uma NFSe vinculada.

Idempotente: se NFSe.pagamento_id ja existe, retorna sem criar duplicata.
Calcula valor_participacao = valor_liquido * percentual_total / 100.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class PagamentoResult:
    nfse_id: int
    pagamento_id: int | None
    motivo: str | None = None


def gerar_pagamento_para_nfse(db: Session, nfse_id: int) -> PagamentoResult:
    row = db.execute(
        text("""
            SELECT id, participacao_id, pagamento_id, valor_liquido, data_emissao, status_matching
            FROM nfse_recebidas WHERE id = :i
        """),
        {"i": nfse_id},
    ).fetchone()
    if row is None:
        raise ValueError(f"NFSe {nfse_id} nao encontrada")
    _, participacao_id, pagamento_id, valor_liquido, data_emissao, _status = row

    if pagamento_id:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=pagamento_id, motivo="ja_vinculada")
    if not participacao_id:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=None, motivo="sem_participacao")

    part = db.execute(
        text("""
            SELECT percentual_captacao, percentual_performance, vinculo_ativo
            FROM participacoes WHERE id = :i
        """),
        {"i": participacao_id},
    ).fetchone()
    if part is None:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=None, motivo="participacao_inexistente")
    pct_cap, pct_perf, ativo = part
    if not ativo:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=None, motivo="vinculo_inativo")

    pct_total = Decimal(str(pct_cap or 0)) + Decimal(str(pct_perf or 0))
    valor_part = (Decimal(str(valor_liquido)) * pct_total / Decimal("100")).quantize(Decimal("0.01"))

    now = datetime.now(timezone.utc)
    db.execute(
        text("""
            INSERT INTO participacao_pagamentos (
                participacao_id, data_recebimento, valor_liquido_recebido,
                valor_participacao, dentro_limite_temporal, observacoes,
                registrado_por, created_at
            ) VALUES (
                :pid, :dt, :vl, :vp, 1, 'NFS-e auto', 'sistema', :now
            )
        """),
        {
            "pid": participacao_id,
            "dt": data_emissao,
            "vl": float(valor_liquido),
            "vp": float(valor_part),
            "now": now,
        },
    )
    new_id = (
        db.execute(text("SELECT last_insert_rowid()")).scalar()
        if db.bind.dialect.name == "sqlite"
        else db.execute(text("SELECT lastval()")).scalar()
    )

    db.execute(
        text("UPDATE nfse_recebidas SET pagamento_id = :p, atualizado_em = :now WHERE id = :i"),
        {"p": new_id, "now": now, "i": nfse_id},
    )
    db.commit()
    return PagamentoResult(nfse_id=nfse_id, pagamento_id=new_id)
