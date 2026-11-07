"""Registrar um recebimento de honorario e a participacao que ele gera.

Unico caminho: a rota manual (POST /api/participacoes/{id}/pagamentos) e a NFS-e
automatica (nfse_pagamento) chamam `registrar`. As regras sao as mesmas nos dois:
imposto pelo tax code, limite temporal por tipo, fim do vinculo e corte 31/07/2024
(participation_calculator). A unica diferenca e' o rateio 50/50 de honorario nao
discriminado, que so existe no manual (`discriminado=False`); NFS-e entra como
discriminada. Dinheiro em Decimal; o chamador faz o commit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import ParticipacaoDB, ParticipacaoPagamentoDB, TaxCodeDB, utcnow
from app.services.pagamento_calculator import calcular_componentes_pagamento, dinheiro
from app.services.participation_calculator import calcular_valor_participacao

TAX_CODE_PADRAO = "PADRAO_1545"


class TaxCodePadraoAusente(Exception):
    """PADRAO_1545 nao esta cadastrado (migration 0005 nao rodou)."""


@dataclass
class Recebimento:
    data_recebimento: date
    valor_bruto: Decimal | float
    discriminado: bool = True
    valor_contratual: Decimal | float | None = None
    status: str = "aguardando_pagamento"
    parcela_num: int = 1
    parcela_total: int = 1
    nf_referencia: str | None = None
    tipo_cobranca: str | None = None
    natureza_pagamento: str | None = None
    tipo_documento: str = "nf"
    observacoes: str | None = None


def tax_code_padrao(db: Session) -> TaxCodeDB | None:
    return (
        db.query(TaxCodeDB)
        .filter(TaxCodeDB.codigo == TAX_CODE_PADRAO, TaxCodeDB.ativo == True)  # noqa: E712
        .first()
    )


def registrar(
    db: Session,
    p: ParticipacaoDB,
    rec: Recebimento,
    *,
    registrado_por: str,
    tax_code: TaxCodeDB | None = None,
    aliquota_total: Decimal | float | None = None,
) -> ParticipacaoPagamentoDB:
    """Calcula e adiciona o pagamento na sessao (flush, sem commit).

    A aliquota vem do `tax_code`; sem ele, de `aliquota_total` (NFS-e em banco sem o
    tax code padrao). Se nenhum dos dois vier, usa o tax code padrao.
    """
    if tax_code is None and aliquota_total is None:
        tax_code = tax_code_padrao(db)
        if tax_code is None:
            raise TaxCodePadraoAusente(TAX_CODE_PADRAO)
    aliquota = tax_code.aliquota_total if tax_code is not None else aliquota_total

    comp = calcular_componentes_pagamento(
        valor_bruto=rec.valor_bruto,
        aliquota_total=aliquota,
        percentual_captacao=p.percentual_captacao,
        percentual_performance=p.percentual_performance,
        discriminado=rec.discriminado,
        valor_contratual_informado=rec.valor_contratual if rec.discriminado else None,
    )
    resultado = calcular_valor_participacao(
        valor_liquido_recebido=comp["valor_contratual"],
        percentual_captacao=p.percentual_captacao,
        percentual_performance=p.percentual_performance,
        tipo_honorario=p.tipo_honorario,
        data_inicio_participacao=p.data_inicio,
        data_recebimento=rec.data_recebimento,
        vinculo_ativo=p.vinculo_ativo,
        data_fim_vinculo=p.data_fim_vinculo,
        eh_contratual=True,
    )

    obs = rec.observacoes or ""
    if resultado.motivo_zerado:
        obs = (obs + f" | {resultado.motivo_zerado}").strip(" |")

    pag = ParticipacaoPagamentoDB(
        participacao_id=p.id,
        data_recebimento=rec.data_recebimento,
        valor_bruto=dinheiro(rec.valor_bruto),
        imposto_total=comp["imposto_total"],
        valor_liquido_recebido=comp["valor_contratual"],
        valor_participacao=resultado.valor_participacao,
        dentro_limite_temporal=resultado.dentro_limite_temporal,
        observacoes=obs or None,
        status=rec.status,
        parcela_num=rec.parcela_num,
        parcela_total=rec.parcela_total,
        nf_referencia=rec.nf_referencia,
        tax_code_id=tax_code.id if tax_code is not None else None,
        tipo_cobranca=rec.tipo_cobranca or p.tipo_honorario,
        natureza_pagamento=rec.natureza_pagamento,
        tipo_documento=rec.tipo_documento,
        registrado_por=registrado_por,
        created_at=utcnow(),
    )
    db.add(pag)
    db.flush()
    return pag
