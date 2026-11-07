from __future__ import annotations

import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import ColaboradorDB, ContractDB, ContractVersionDB, get_db
from app.services.arquivo_contrato import ArquivoNaoEncontrado
from app.services.docuseal import link_assinatura
from app.services import assinatura, resultado_assinatura, servicos_externos
from app.utils.participacao import linhas_participacao
from app.utils.erros import MSG_ERRO_DOCUSEAL, MSG_ERRO_INTERNO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docuseal", tags=["DocuSeal"])

class DocuSealRequest(BaseModel):
    contract_id: str
    signatarios: list[dict[str, str]]

    # O front manda null em campos opcionais (ex.: phone sem WhatsApp); o pydantic
    # recusava com "Input should be a valid string" e o envio nao saia.
    @field_validator("signatarios", mode="before")
    @classmethod
    def _sem_nulos(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return v
        return [
            {k: str(x) for k, x in s.items() if x is not None} if isinstance(s, dict) else s
            for s in v
        ]


class DocuSealResponse(BaseModel):
    success: bool
    message: str
    submission_id: str | None = None
    # Contratantes com link e WhatsApp: a tela abre o WhatsApp logo apos o envio.
    whatsapp: list[dict[str, str]] = []


def socio_sugerido(form_data_json: str | None, db: Session) -> ColaboradorDB | None:
    """Socio pre-selecionado na tela para assinar pelo escritorio (o usuario pode trocar).

    O responsavel pela gestao, se for socio; senao o primeiro socio entre os que
    recebem participacao (regra do PR #74).
    """
    from app.models.contract import Participacao

    if not form_data_json:
        return None
    try:
        form_data = json.loads(form_data_json)
    except ValueError:
        return None

    socios = (
        db.query(ColaboradorDB)
        .filter(
            ColaboradorDB.papel == "socio",
            ColaboradorDB.ativo.is_(True),
            ColaboradorDB.email.isnot(None),
        )
        .all()
    )

    try:
        participacao = Participacao(**(form_data.get("participacao") or {}))
    except Exception:
        return None
    por_nome = {s.nome: s for s in socios}
    for nome in [participacao.responsavel_gestao] + [p.nome for p in participacao.participantes]:
        socio = por_nome.get((nome or "").strip())
        if socio:
            return socio
    return None


@router.post("/send-for-signature", response_model=DocuSealResponse)
async def send_for_signature(
    data: DocuSealRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocuSealResponse:
    """Send contract for digital signature via DocuSeal."""
    try:
        r = await assinatura.enviar(db, data.contract_id, data.signatarios, user.email)
    except assinatura.EnvioInvalido as e:
        raise HTTPException(400, str(e))
    except ArquivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Contract file not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DocuSeal error: %s", e)
        raise HTTPException(status_code=500, detail=MSG_ERRO_INTERNO)
    return DocuSealResponse(
        success=r.success,
        message=r.message,
        submission_id=r.submission_id,
        whatsapp=[_assinante_para_tela(s) for s in r.contratantes],
    )


# ── Webhook (no auth — called externally by DocuSeal) ───────────


def _assinante_para_tela(s: dict[str, Any]) -> dict[str, str]:
    """Um signatario do DocuSeal com o link de assinatura e o WhatsApp dele."""
    return {
        "role": s.get("role", ""),
        "name": s.get("name", ""),
        "email": s.get("email", ""),
        # A criacao traz embed_src; a consulta so' o slug.
        "link": s.get("embed_src") or link_assinatura(settings.docuseal_base_url, s.get("slug") or ""),
        "whatsapp": s.get("phone") or "",
    }


def _pendentes_docuseal(status_data: dict[str, Any]) -> list[dict[str, str]]:
    """Signatarios que ainda nao assinaram nem recusaram, pra mostrar na tela."""
    submitters = status_data.get("submitters") or []
    return [
        _assinante_para_tela(s)
        for s in submitters
        if not s.get("completed_at") and not s.get("declined_at")
    ]


class DocuSealWebhookPayload(BaseModel):
    event_type: str
    data: dict[str, Any] = {}


@router.post("/webhook")
async def docuseal_webhook(
    payload: DocuSealWebhookPayload,
    x_docuseal_secret: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Receive webhook events from DocuSeal.

    submission.completed: data.id e' a submissao. A recusa chega como form.declined (o DocuSeal nao
    tem submission.declined): ali data.id e' o do SIGNATARIO e a submissao vem em data.submission.id.
    """
    # Validate webhook secret
    segredo = settings.docuseal_webhook_secret
    if not segredo or not hmac.compare_digest(x_docuseal_secret or "", segredo):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    event_type = payload.event_type
    data = payload.data
    if event_type == "form.declined":
        submission_id = str((data.get("submission") or {}).get("id", ""))
    else:
        submission_id = str(data.get("id", data.get("submission_id", "")))

    logger.info("DocuSeal webhook received: event=%s submission_id=%s", event_type, submission_id)

    if event_type not in ("submission.completed", "form.declined"):
        return {"status": "ignored", "event_type": event_type}

    new_status = "assinado" if event_type == "submission.completed" else "recusado"

    # Find the contract version that matches this submission
    version = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.docuseal_submission_id == submission_id)
        .first()
    )
    if not version:
        logger.warning("No contract version found for submission_id=%s", submission_id)
        return {"status": "not_found", "submission_id": submission_id}

    contract = db.query(ContractDB).filter(ContractDB.contract_id == version.contract_id).first()
    if contract:
        await resultado_assinatura.aplicar_conclusao(
            contract,
            version,
            new_status,
            f"webhook_{new_status}",
            f"DocuSeal webhook: {event_type} (submission {submission_id})",
            db,
        )

    return {"status": "ok", "new_status": new_status}


# ── Status check (authenticated) ────────────────────────────────


class DocuSealStatusResponse(BaseModel):
    contract_id: str
    submission_id: str
    status: dict[str, Any]


@router.get("/{contract_id}/status", response_model=DocuSealStatusResponse)
async def get_docuseal_status(
    contract_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check the signing status of a contract via DocuSeal API."""
    latest_version = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract_id)
        .order_by(ContractVersionDB.version_number.desc())
        .first()
    )

    if not latest_version or not latest_version.docuseal_submission_id:
        raise HTTPException(status_code=404, detail="No DocuSeal submission found for this contract")

    submission_id = latest_version.docuseal_submission_id
    service = servicos_externos.get_docuseal_service()
    status_data = await service.get_submission_status(submission_id)

    return DocuSealStatusResponse(
        contract_id=contract_id,
        submission_id=submission_id,
        status=status_data,
    )


class PendenteSigner(BaseModel):
    role: str
    name: str
    email: str
    link: str = ""
    whatsapp: str = ""


class SincronizacaoResponse(BaseModel):
    contract_id: str
    status: str
    alterado: bool
    detalhe: str
    pendentes: list[PendenteSigner] = []


@router.post("/{contract_id}/cancelar-envio")
async def cancelar_envio_assinatura(
    contract_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Arquiva a submissao no DocuSeal (o link enviado deixa de valer) e volta o contrato a rascunho.

    So para contrato 'enviado'. Se o DocuSeal recusar ou falhar, nada muda aqui.
    """
    from app.routers.contracts import _check_access

    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    _check_access(contract, user)
    try:
        await resultado_assinatura.cancelar_envio(db, contract, user.email)
    except resultado_assinatura.EnvioNaoCancelavel as e:
        raise HTTPException(status_code=409, detail=str(e))
    except resultado_assinatura.DocuSealNaoConfirmou as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"success": True, "status": contract.status}


@router.post("/{contract_id}/sincronizar", response_model=SincronizacaoResponse)
async def sincronizar_status_assinatura(
    contract_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Le a submissao no DocuSeal e conclui o contrato se todos ja' assinaram.

    O webhook e' o caminho normal, mas ele depende de configuracao externa
    (docuseal_webhook_secret e o webhook cadastrado no DocuSeal) e de a chamada
    chegar. Quando falta qualquer uma das duas pontas, o contrato ficava preso em
    "enviado" para sempre, mesmo com todas as assinaturas colhidas — e so' dava
    para destravar mudando o status na mao. Aqui o proprio sistema pergunta ao
    DocuSeal em vez de esperar ser avisado.
    """
    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    version = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract_id)
        .order_by(ContractVersionDB.version_number.desc())
        .first()
    )
    if not version or not version.docuseal_submission_id:
        raise HTTPException(status_code=404, detail="Contrato não foi enviado para assinatura")

    status_anterior = contract.status
    service = servicos_externos.get_docuseal_service()
    try:
        status_data = await service.get_submission_status(version.docuseal_submission_id)
    except Exception as e:
        logger.warning("Falha ao consultar submissao %s: %s", version.docuseal_submission_id, e)
        raise HTTPException(status_code=502, detail=MSG_ERRO_DOCUSEAL)

    conclusao = resultado_assinatura.conclusao_docuseal(status_data)
    if not conclusao:
        pendentes = _pendentes_docuseal(status_data)
        nomes = ", ".join(f"{p['name']} ({p['role']})" for p in pendentes if p["name"])
        detalhe = (
            f"Ainda faltam assinar: {nomes}."
            if nomes
            else "Ainda há assinaturas pendentes no DocuSeal."
        )
        return SincronizacaoResponse(
            contract_id=contract_id,
            status=contract.status,
            alterado=False,
            detalhe=detalhe,
            pendentes=pendentes,
        )

    await resultado_assinatura.aplicar_conclusao(
        contract,
        version,
        conclusao,
        f"sync_{conclusao}",
        f"Status confirmado junto ao DocuSeal (submission {version.docuseal_submission_id})",
        db,
    )

    alterado = contract.status != status_anterior
    return SincronizacaoResponse(
        contract_id=contract_id,
        status=contract.status,
        alterado=alterado,
        detalhe=(
            "Todas as partes assinaram — contrato concluído."
            if conclusao == "assinado"
            else "Assinatura recusada no DocuSeal."
        ) if alterado else "O status já estava atualizado.",
    )
