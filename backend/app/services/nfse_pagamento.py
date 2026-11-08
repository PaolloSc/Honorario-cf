"""Cria registro em participacao_pagamentos para uma NFSe vinculada.

Idempotente: se NFSe.pagamento_id ja existe, retorna sem criar duplicata.
O calculo e' o mesmo do registro manual (pagamento_participacao.registrar): a NFS-e
entra como recebimento discriminado, com valor_bruto = valor dos servicos e o tax code
padrao. Se o banco nao tem o tax code padrao, a aliquota sai da propria nota.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import ParticipacaoDB
from app.models.nfse_db import NFSeRecebidaDB
from app.services.pagamento_participacao import Recebimento, registrar, tax_code_padrao


@dataclass
class PagamentoResult:
    nfse_id: int
    pagamento_id: int | None
    motivo: str | None = None


def gerar_pagamento_para_nfse(db: Session, nfse_id: int) -> PagamentoResult:
    nota = db.get(NFSeRecebidaDB, nfse_id)
    if nota is None:
        raise ValueError(f"NFSe {nfse_id} nao encontrada")
    participacao_id, pagamento_id = nota.participacao_id, nota.pagamento_id
    valor_servicos, valor_liquido, data_emissao, numero = (
        nota.valor_servicos, nota.valor_liquido, nota.data_emissao, nota.numero,
    )

    if pagamento_id:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=pagamento_id, motivo="ja_vinculada")
    if not participacao_id:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=None, motivo="sem_participacao")

    p = db.get(ParticipacaoDB, participacao_id)
    if p is None:
        return PagamentoResult(nfse_id=nfse_id, pagamento_id=None, motivo="participacao_inexistente")

    bruto = Decimal(str(valor_servicos))
    tc = tax_code_padrao(db)
    aliquota = None
    if tc is None:  # banco sem o tax code padrao: usa a retencao da propria nota
        aliquota = (bruto - Decimal(str(valor_liquido))) / bruto if bruto else Decimal(0)

    if isinstance(data_emissao, str):
        data_emissao = datetime.fromisoformat(data_emissao).date()
    elif isinstance(data_emissao, datetime):
        data_emissao = data_emissao.date()

    pag = registrar(
        db,
        p,
        Recebimento(
            data_recebimento=data_emissao,
            valor_bruto=bruto,
            nf_referencia=str(numero) if numero else None,
            observacoes="NFS-e auto",
        ),
        registrado_por="sistema",
        tax_code=tc,
        aliquota_total=aliquota,
    )
    nota.pagamento_id = pag.id
    nota.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    return PagamentoResult(nfse_id=nfse_id, pagamento_id=pag.id)
