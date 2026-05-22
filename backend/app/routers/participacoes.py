"""Router de participações internas — acesso restrito ao setor financeiro."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_financeiro
from app.database import (
    ContractDB,
    ParticipacaoDB,
    ParticipacaoPagamentoDB,
    get_db,
    utcnow,
)
from app.services.participation_calculator import (
    DATA_VIGENCIA,
    LIMITES_TEMPORAIS_ANOS,
    calcular_valor_participacao,
    split_contratual_sucumbencial,
    validar_participacao,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/participacoes", tags=["Participações (Financeiro)"])


# ── Schemas ───────────────────────────────────────────────────────


class CriarParticipacaoRequest(BaseModel):
    contract_id: str
    beneficiario_email: str
    beneficiario_nome: str = ""
    tipo_honorario: str  # hora|partido|mensalidade|exito|prolabore|misto
    percentual_captacao: float = 0.0
    percentual_performance: float = 0.0
    motivo_captacao: Optional[str] = None
    motivo_performance: Optional[str] = None
    natureza: str = "contratual"  # contratual|societario
    cliente_cpf_cnpj: Optional[str] = None
    data_inicio: date
    aprovado_por: Optional[str] = None
    observacoes: Optional[str] = None


class ParticipacaoResponse(BaseModel):
    id: int
    contract_id: str
    beneficiario_email: str
    beneficiario_nome: str
    tipo_honorario: str
    percentual_captacao: float
    percentual_performance: float
    percentual_total: float
    motivo_captacao: Optional[str]
    motivo_performance: Optional[str]
    natureza: str
    cliente_cpf_cnpj: Optional[str]
    data_inicio: str
    vinculo_ativo: bool
    data_fim_vinculo: Optional[str]
    aprovado_por: Optional[str]
    aprovada: bool
    observacoes: Optional[str]
    limite_temporal_anos: Optional[int]
    data_limite_temporal: Optional[str]
    total_pago: float
    created_at: str


class ListaParticipacoesResponse(BaseModel):
    participacoes: list[ParticipacaoResponse]
    total: int


PAGAMENTO_STATUS_VALIDOS = ("a_receber", "aguardando_pagamento", "pago")


class RegistrarPagamentoRequest(BaseModel):
    data_recebimento: date
    valor_bruto: float
    discriminado: bool = True  # alvará/acordo discrimina contratual x sucumbencial?
    valor_contratual: Optional[float] = None  # se discriminado=True
    observacoes: Optional[str] = None
    status: str = "aguardando_pagamento"  # a_receber | aguardando_pagamento | pago


class AtualizarStatusRequest(BaseModel):
    status: str  # a_receber | aguardando_pagamento | pago


class CalculoSimulacaoRequest(BaseModel):
    tipo_honorario: str
    percentual_captacao: float = 0.0
    percentual_performance: float = 0.0
    data_inicio_participacao: date
    data_recebimento: date
    valor_liquido_recebido: float
    vinculo_ativo: bool = True
    data_fim_vinculo: Optional[date] = None
    eh_contratual: bool = True


class CalculoResponse(BaseModel):
    valor_participacao: float
    dentro_limite_temporal: bool
    vinculo_ativo: bool
    motivo_zerado: Optional[str]
    percentual_aplicado: float


class PagamentoResponse(BaseModel):
    id: int
    participacao_id: int
    data_recebimento: str
    valor_liquido_recebido: float
    valor_participacao: float
    dentro_limite_temporal: bool
    observacoes: Optional[str]
    status: str
    created_at: str


class ResumoParticipacaoResponse(BaseModel):
    participacao: ParticipacaoResponse
    pagamentos: list[PagamentoResponse]
    total_recebido_liquido: float
    total_participacao: float


# ── Helpers ───────────────────────────────────────────────────────


def _validar_captacao_elegivel(
    db: Session,
    cliente_cpf_cnpj: Optional[str],
    contract_id: str,
    data_inicio: date,
) -> list[str]:
    """Captação exige: novo contrato, sem contrato vigente e sem faturamento últimos 36 meses."""
    erros: list[str] = []
    if not cliente_cpf_cnpj:
        erros.append(
            "Captação exige CPF/CNPJ do cliente para validar ausência de contrato vigente "
            "e faturamento nos últimos 36 meses."
        )
        return erros

    cutoff = data_inicio - timedelta(days=36 * 30)
    # Existe outro contrato deste cliente nos últimos 36 meses?
    outros = (
        db.query(ParticipacaoDB)
        .filter(
            ParticipacaoDB.cliente_cpf_cnpj == cliente_cpf_cnpj,
            ParticipacaoDB.contract_id != contract_id,
            ParticipacaoDB.created_at >= cutoff,
        )
        .all()
    )
    if outros:
        erros.append(
            "Cliente possui contrato/participação registrado nos últimos 36 meses — "
            "não elegível para Captação."
        )
    return erros


def _to_response(p: ParticipacaoDB, total_pago: float = 0.0) -> ParticipacaoResponse:
    limite_anos = LIMITES_TEMPORAIS_ANOS.get(p.tipo_honorario)
    data_limite = None
    if limite_anos is not None:
        try:
            data_limite = p.data_inicio.replace(year=p.data_inicio.year + limite_anos).isoformat()
        except ValueError:
            data_limite = p.data_inicio.replace(
                year=p.data_inicio.year + limite_anos, day=28
            ).isoformat()
    return ParticipacaoResponse(
        id=p.id,
        contract_id=p.contract_id,
        beneficiario_email=p.beneficiario_email,
        beneficiario_nome=p.beneficiario_nome,
        tipo_honorario=p.tipo_honorario,
        percentual_captacao=p.percentual_captacao,
        percentual_performance=p.percentual_performance,
        percentual_total=p.percentual_captacao + p.percentual_performance,
        motivo_captacao=p.motivo_captacao,
        motivo_performance=p.motivo_performance,
        natureza=p.natureza,
        cliente_cpf_cnpj=p.cliente_cpf_cnpj,
        data_inicio=p.data_inicio.isoformat(),
        vinculo_ativo=p.vinculo_ativo,
        data_fim_vinculo=p.data_fim_vinculo.isoformat() if p.data_fim_vinculo else None,
        aprovado_por=p.aprovado_por,
        aprovada=bool(p.aprovada),
        observacoes=p.observacoes,
        limite_temporal_anos=limite_anos,
        data_limite_temporal=data_limite,
        total_pago=round(total_pago, 2),
        created_at=p.created_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────


class ContratoPendenteResponse(BaseModel):
    contract_id: str
    status: str
    client_name: str
    client_email: str
    created_by: Optional[str]
    created_at: str
    updated_at: str
    tem_rascunho: bool
    participacao_id: Optional[int] = None
    tipo_honorario_inferido: Optional[str] = None
    cliente_cpf_cnpj: Optional[str] = None


class ListaContratosPendentesResponse(BaseModel):
    contratos: list[ContratoPendenteResponse]
    total: int


class AprovarParticipacaoRequest(BaseModel):
    percentual_captacao: float = 0.0
    percentual_performance: float = 0.0
    motivo_captacao: Optional[str] = None
    motivo_performance: Optional[str] = None
    tipo_honorario: Optional[str] = None  # permite ajuste do tipo inferido
    cliente_cpf_cnpj: Optional[str] = None
    aprovado_por: Optional[str] = None
    natureza: Optional[str] = None
    observacoes: Optional[str] = None


@router.get("/regras")
def get_regras(user: CurrentUser = Depends(require_financeiro)):
    """Retorna as regras vigentes (consumidas pela UI para exibir lembretes)."""
    return {
        "vigencia_inicio": DATA_VIGENCIA.isoformat(),
        "limite_captacao_pct": 20,
        "limite_performance_pct": 20,
        "limite_combo_pct": 40,
        "limites_temporais_anos": {
            k: (v if v is not None else "sem_limite") for k, v in LIMITES_TEMPORAIS_ANOS.items()
        },
        "honorarios_aplicaveis": "contratuais (sucumbenciais excluídos)",
        "regra_alvara_indiscriminado": "50% contratual / 50% sucumbencial",
        "captacao_criterios": (
            "novo contrato com CPF/CNPJ sem contrato vigente e sem faturamento nos últimos 36 meses"
        ),
        "performance_criterios": (
            "atuação excepcional reconhecida OU criação de nova área/serviço aprovada pelos sócios"
        ),
        "excecoes": "parceiros técnicos/comerciais não se aplicam",
        "condicao_pagamento": "vínculo contratual ou societário ativo com o escritório",
    }


@router.post("", response_model=ParticipacaoResponse)
def criar_participacao(
    body: CriarParticipacaoRequest,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    # 1. Validações de domínio
    v = validar_participacao(
        body.tipo_honorario,
        body.percentual_captacao,
        body.percentual_performance,
        body.data_inicio,
    )
    if not v.ok:
        raise HTTPException(422, "; ".join(v.erros))

    # 2. Captação exige checagem extra
    if body.percentual_captacao > 0:
        erros_cap = _validar_captacao_elegivel(
            db, body.cliente_cpf_cnpj, body.contract_id, body.data_inicio
        )
        if erros_cap:
            raise HTTPException(422, "; ".join(erros_cap))

    # 3. Performance exige justificativa e aprovação
    if body.percentual_performance > 0:
        if not (body.motivo_performance and body.aprovado_por):
            raise HTTPException(
                422,
                "Performance exige motivo e aprovação dos sócios (campo aprovado_por).",
            )

    # 4. Contrato precisa existir
    contract = db.query(ContractDB).filter(ContractDB.contract_id == body.contract_id).first()
    if not contract:
        raise HTTPException(404, f"Contrato {body.contract_id} não encontrado")

    if body.natureza not in ("contratual", "societario"):
        raise HTTPException(422, "natureza deve ser 'contratual' ou 'societario'")

    p = ParticipacaoDB(
        contract_id=body.contract_id,
        beneficiario_email=body.beneficiario_email,
        beneficiario_nome=body.beneficiario_nome,
        tipo_honorario=body.tipo_honorario,
        percentual_captacao=body.percentual_captacao,
        percentual_performance=body.percentual_performance,
        motivo_captacao=body.motivo_captacao,
        motivo_performance=body.motivo_performance,
        natureza=body.natureza,
        cliente_cpf_cnpj=body.cliente_cpf_cnpj,
        data_inicio=body.data_inicio,
        vinculo_ativo=True,
        aprovado_por=body.aprovado_por,
        aprovada=True,
        observacoes=body.observacoes,
        created_by=user.email,
        created_at=utcnow(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    logger.info(
        "Participação criada id=%s contrato=%s beneficiario=%s cap=%s perf=%s por=%s",
        p.id, p.contract_id, p.beneficiario_email,
        p.percentual_captacao, p.percentual_performance, user.email,
    )
    return _to_response(p, 0.0)


@router.get("", response_model=ListaParticipacoesResponse)
def listar_participacoes(
    contract_id: Optional[str] = None,
    beneficiario_email: Optional[str] = None,
    apenas_ativos: bool = False,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    q = db.query(ParticipacaoDB)
    if contract_id:
        q = q.filter(ParticipacaoDB.contract_id == contract_id)
    if beneficiario_email:
        q = q.filter(ParticipacaoDB.beneficiario_email == beneficiario_email)
    if apenas_ativos:
        q = q.filter(ParticipacaoDB.vinculo_ativo == True)  # noqa: E712
    items = q.order_by(ParticipacaoDB.created_at.desc()).all()

    out: list[ParticipacaoResponse] = []
    for p in items:
        total = sum(pag.valor_participacao for pag in p.pagamentos)
        out.append(_to_response(p, total))
    return ListaParticipacoesResponse(participacoes=out, total=len(out))


@router.get("/{pid}/resumo", response_model=ResumoParticipacaoResponse)
def resumo_participacao(
    pid: int,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    p = db.query(ParticipacaoDB).filter(ParticipacaoDB.id == pid).first()
    if not p:
        raise HTTPException(404, "Participação não encontrada")

    pagamentos = [
        PagamentoResponse(
            id=pag.id,
            participacao_id=pag.participacao_id,
            data_recebimento=pag.data_recebimento.isoformat(),
            valor_liquido_recebido=pag.valor_liquido_recebido,
            valor_participacao=pag.valor_participacao,
            dentro_limite_temporal=pag.dentro_limite_temporal,
            observacoes=pag.observacoes,
            status=pag.status,
            created_at=pag.created_at.isoformat(),
        )
        for pag in p.pagamentos
    ]
    total_liquido = sum(x.valor_liquido_recebido for x in pagamentos)
    total_part = sum(x.valor_participacao for x in pagamentos)

    return ResumoParticipacaoResponse(
        participacao=_to_response(p, total_part),
        pagamentos=pagamentos,
        total_recebido_liquido=round(total_liquido, 2),
        total_participacao=round(total_part, 2),
    )


@router.post("/{pid}/pagamentos", response_model=PagamentoResponse)
def registrar_pagamento(
    pid: int,
    body: RegistrarPagamentoRequest,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    p = db.query(ParticipacaoDB).filter(ParticipacaoDB.id == pid).first()
    if not p:
        raise HTTPException(404, "Participação não encontrada")

    valor_contratual, _ = split_contratual_sucumbencial(
        body.valor_bruto, body.discriminado, body.valor_contratual
    )

    resultado = calcular_valor_participacao(
        valor_liquido_recebido=valor_contratual,
        percentual_captacao=p.percentual_captacao,
        percentual_performance=p.percentual_performance,
        tipo_honorario=p.tipo_honorario,
        data_inicio_participacao=p.data_inicio,
        data_recebimento=body.data_recebimento,
        vinculo_ativo=p.vinculo_ativo,
        data_fim_vinculo=p.data_fim_vinculo,
        eh_contratual=True,  # já separamos a parcela contratual acima
    )

    if body.status not in PAGAMENTO_STATUS_VALIDOS:
        raise HTTPException(422, f"status inválido. Aceitos: {PAGAMENTO_STATUS_VALIDOS}")

    pag = ParticipacaoPagamentoDB(
        participacao_id=p.id,
        data_recebimento=body.data_recebimento,
        valor_liquido_recebido=valor_contratual,
        valor_participacao=resultado.valor_participacao,
        dentro_limite_temporal=resultado.dentro_limite_temporal,
        observacoes=body.observacoes
        + (f" | {resultado.motivo_zerado}" if resultado.motivo_zerado else "")
        if body.observacoes
        else resultado.motivo_zerado,
        status=body.status,
        registrado_por=user.email,
        created_at=utcnow(),
    )
    db.add(pag)
    db.commit()
    db.refresh(pag)
    return PagamentoResponse(
        id=pag.id,
        participacao_id=pag.participacao_id,
        data_recebimento=pag.data_recebimento.isoformat(),
        valor_liquido_recebido=pag.valor_liquido_recebido,
        valor_participacao=pag.valor_participacao,
        dentro_limite_temporal=pag.dentro_limite_temporal,
        observacoes=pag.observacoes,
        status=pag.status,
        created_at=pag.created_at.isoformat(),
    )


@router.patch("/pagamentos/{pag_id}/status", response_model=PagamentoResponse)
def atualizar_status_pagamento(
    pag_id: int,
    body: AtualizarStatusRequest,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    """Workflow do pagamento: a_receber -> aguardando_pagamento -> pago.

    Transição livre (estorno possível). Valida apenas valor do enum.
    """
    if body.status not in PAGAMENTO_STATUS_VALIDOS:
        raise HTTPException(422, f"status inválido. Aceitos: {PAGAMENTO_STATUS_VALIDOS}")

    pag = (
        db.query(ParticipacaoPagamentoDB)
        .filter(ParticipacaoPagamentoDB.id == pag_id)
        .first()
    )
    if not pag:
        raise HTTPException(404, "Pagamento não encontrado")

    pag.status = body.status
    db.commit()
    db.refresh(pag)
    return PagamentoResponse(
        id=pag.id,
        participacao_id=pag.participacao_id,
        data_recebimento=pag.data_recebimento.isoformat(),
        valor_liquido_recebido=pag.valor_liquido_recebido,
        valor_participacao=pag.valor_participacao,
        dentro_limite_temporal=pag.dentro_limite_temporal,
        observacoes=pag.observacoes,
        status=pag.status,
        created_at=pag.created_at.isoformat(),
    )


@router.post("/{pid}/encerrar-vinculo", response_model=ParticipacaoResponse)
def encerrar_vinculo(
    pid: int,
    data_fim: date = Query(...),
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    p = db.query(ParticipacaoDB).filter(ParticipacaoDB.id == pid).first()
    if not p:
        raise HTTPException(404, "Participação não encontrada")
    p.vinculo_ativo = False
    p.data_fim_vinculo = data_fim
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    total = sum(pag.valor_participacao for pag in p.pagamentos)
    return _to_response(p, total)


@router.get("/contratos-pendentes", response_model=ListaContratosPendentesResponse)
def listar_contratos_pendentes(
    incluir_rascunhos: bool = True,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    """Plano B: lista contratos que ainda precisam de tratamento financeiro.

    - Contratos sem nenhuma participação cadastrada
    - Contratos com participações rascunho (aprovada=False) — apenas se incluir_rascunhos=True
    """
    contracts = db.query(ContractDB).order_by(ContractDB.created_at.desc()).all()
    out: list[ContratoPendenteResponse] = []
    for c in contracts:
        parts = (
            db.query(ParticipacaoDB)
            .filter(ParticipacaoDB.contract_id == c.contract_id)
            .all()
        )
        if not parts:
            out.append(
                ContratoPendenteResponse(
                    contract_id=c.contract_id,
                    status=c.status,
                    client_name=c.client_name,
                    client_email=c.client_email,
                    created_by=c.created_by,
                    created_at=c.created_at.isoformat(),
                    updated_at=c.updated_at.isoformat(),
                    tem_rascunho=False,
                )
            )
            continue
        rascunho = next((p for p in parts if not p.aprovada), None)
        if rascunho and incluir_rascunhos:
            out.append(
                ContratoPendenteResponse(
                    contract_id=c.contract_id,
                    status=c.status,
                    client_name=c.client_name,
                    client_email=c.client_email,
                    created_by=c.created_by,
                    created_at=c.created_at.isoformat(),
                    updated_at=c.updated_at.isoformat(),
                    tem_rascunho=True,
                    participacao_id=rascunho.id,
                    tipo_honorario_inferido=rascunho.tipo_honorario,
                    cliente_cpf_cnpj=rascunho.cliente_cpf_cnpj,
                )
            )
    return ListaContratosPendentesResponse(contratos=out, total=len(out))


@router.post("/{pid}/aprovar", response_model=ParticipacaoResponse)
def aprovar_participacao(
    pid: int,
    body: AprovarParticipacaoRequest,
    user: CurrentUser = Depends(require_financeiro),
    db: Session = Depends(get_db),
):
    """Setor financeiro completa percentuais/motivos e aprova rascunho criado pelo wizard."""
    p = db.query(ParticipacaoDB).filter(ParticipacaoDB.id == pid).first()
    if not p:
        raise HTTPException(404, "Participação não encontrada")
    if p.aprovada:
        raise HTTPException(409, "Participação já aprovada")

    # Aplica overrides
    if body.tipo_honorario:
        p.tipo_honorario = body.tipo_honorario
    if body.cliente_cpf_cnpj is not None:
        p.cliente_cpf_cnpj = body.cliente_cpf_cnpj
    if body.natureza:
        if body.natureza not in ("contratual", "societario"):
            raise HTTPException(422, "natureza inválida")
        p.natureza = body.natureza
    p.percentual_captacao = body.percentual_captacao
    p.percentual_performance = body.percentual_performance
    p.motivo_captacao = body.motivo_captacao
    p.motivo_performance = body.motivo_performance
    p.aprovado_por = body.aprovado_por
    if body.observacoes is not None:
        p.observacoes = body.observacoes

    # Valida regras
    v = validar_participacao(
        p.tipo_honorario,
        p.percentual_captacao,
        p.percentual_performance,
        p.data_inicio,
    )
    if not v.ok:
        raise HTTPException(422, "; ".join(v.erros))

    if p.percentual_captacao > 0:
        erros_cap = _validar_captacao_elegivel(
            db, p.cliente_cpf_cnpj, p.contract_id, p.data_inicio
        )
        if erros_cap:
            raise HTTPException(422, "; ".join(erros_cap))

    if p.percentual_performance > 0 and not (p.motivo_performance and p.aprovado_por):
        raise HTTPException(
            422, "Performance exige motivo e aprovação dos sócios (aprovado_por)."
        )

    p.aprovada = True
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    total = sum(pag.valor_participacao for pag in p.pagamentos)
    return _to_response(p, total)


@router.post("/simular", response_model=CalculoResponse)
def simular(
    body: CalculoSimulacaoRequest,
    user: CurrentUser = Depends(require_financeiro),
):
    v = validar_participacao(
        body.tipo_honorario,
        body.percentual_captacao,
        body.percentual_performance,
        body.data_inicio_participacao,
    )
    if not v.ok:
        raise HTTPException(422, "; ".join(v.erros))
    r = calcular_valor_participacao(
        valor_liquido_recebido=body.valor_liquido_recebido,
        percentual_captacao=body.percentual_captacao,
        percentual_performance=body.percentual_performance,
        tipo_honorario=body.tipo_honorario,
        data_inicio_participacao=body.data_inicio_participacao,
        data_recebimento=body.data_recebimento,
        vinculo_ativo=body.vinculo_ativo,
        data_fim_vinculo=body.data_fim_vinculo,
        eh_contratual=body.eh_contratual,
    )
    return CalculoResponse(
        valor_participacao=r.valor_participacao,
        dentro_limite_temporal=r.dentro_limite_temporal,
        vinculo_ativo=r.vinculo_ativo,
        motivo_zerado=r.motivo_zerado,
        percentual_aplicado=body.percentual_captacao + body.percentual_performance,
    )
