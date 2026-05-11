from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.config import BACKEND_DIR, settings
from app.database import AuditLogDB, ContractDB, ContractVersionDB, get_db, utcnow
from app.services.docuseal import DocuSealService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docuseal", tags=["DocuSeal"])

DOCUSEAL_WEBHOOK_SECRET = os.getenv("DOCUSEAL_WEBHOOK_SECRET", "")


class DocuSealRequest(BaseModel):
    contract_id: str
    signatarios: list[dict[str, str]]


class DocuSealResponse(BaseModel):
    success: bool
    message: str
    submission_id: str | None = None


_docuseal_service: DocuSealService | None = None


def get_docuseal_service() -> DocuSealService:
    global _docuseal_service
    if _docuseal_service is None:
        _docuseal_service = DocuSealService()
    return _docuseal_service


def resolve_backend_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


@router.post("/send-for-signature", response_model=DocuSealResponse)
async def send_for_signature(
    data: DocuSealRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocuSealResponse:
    """Send contract for digital signature via DocuSeal."""
    try:
        service = get_docuseal_service()

        # For now, create a simple template from the contract
        # In production, you'd upload the actual file and create a template first
        filepath = resolve_backend_path(settings.output_dir) / f"contrato_{data.contract_id}.docx"
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Contract file not found")

        result = await service.create_template_from_docx(
            filepath=str(filepath),
            name=f"Contrato Honorarios {data.contract_id}",
        )

        template_id = result.get("id")
        if not template_id:
            return DocuSealResponse(
                success=False,
                message="Failed to create DocuSeal template",
            )

        # Send for signature
        sign_result = await service.send_for_signature(
            template_id=template_id,
            signatarios=data.signatarios,
            send_email=True,
        )

        if sign_result.get("success"):
            submission = sign_result.get("submission", {})
            submission_id = submission.get("id")

            # Update DB: status + audit log
            contract = db.query(ContractDB).filter(ContractDB.contract_id == data.contract_id).first()
            if contract:
                contract.status = "enviado"
                contract.updated_at = utcnow()
                # Save submission_id on latest version
                latest_ver = (
                    db.query(ContractVersionDB)
                    .filter(ContractVersionDB.contract_id == data.contract_id)
                    .order_by(ContractVersionDB.version_number.desc())
                    .first()
                )
                if latest_ver:
                    latest_ver.docuseal_submission_id = str(submission_id) if submission_id else None
                db.add(AuditLogDB(
                    contract_id=data.contract_id,
                    action="envio_assinatura",
                    detail=f"Enviado para assinatura via DocuSeal (submission {submission_id})",
                    version_number=contract.current_version,
                    user_email=user.email,
                    created_at=utcnow(),
                ))
                db.commit()

            return DocuSealResponse(
                success=True,
                message="Documento enviado para assinatura com sucesso",
                submission_id=str(submission_id) if submission_id else None,
            )
        else:
            return DocuSealResponse(
                success=False,
                message=sign_result.get("message", "Erro ao enviar para assinatura"),
            )

    except Exception as e:
        logger.error("DocuSeal error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Webhook (no auth — called externally by DocuSeal) ───────────


class DocuSealWebhookPayload(BaseModel):
    event_type: str
    data: dict[str, Any] = {}


@router.post("/webhook")
async def docuseal_webhook(
    payload: DocuSealWebhookPayload,
    x_docuseal_secret: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Receive webhook events from DocuSeal (submission.completed / submission.declined)."""
    # Validate webhook secret
    if not DOCUSEAL_WEBHOOK_SECRET or x_docuseal_secret != DOCUSEAL_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    event_type = payload.event_type
    data = payload.data
    submission_id = str(data.get("id", data.get("submission_id", "")))

    logger.info("DocuSeal webhook received: event=%s submission_id=%s", event_type, submission_id)

    if event_type not in ("submission.completed", "submission.declined"):
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
        contract.status = new_status
        contract.updated_at = utcnow()
        db.add(AuditLogDB(
            contract_id=contract.contract_id,
            action=f"webhook_{new_status}",
            detail=f"DocuSeal webhook: {event_type} (submission {submission_id})",
            version_number=version.version_number,
            created_at=utcnow(),
        ))
        db.commit()
        logger.info("Contract %s updated to status '%s'", contract.contract_id, new_status)

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
    service = get_docuseal_service()
    status_data = await service.get_submission_status(int(submission_id))

    return DocuSealStatusResponse(
        contract_id=contract_id,
        submission_id=submission_id,
        status=status_data,
    )
