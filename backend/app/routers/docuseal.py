from __future__ import annotations

import json
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
from app.services.azure_email import AzureEmailService
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
_email_service: AzureEmailService | None = None


def get_docuseal_service() -> DocuSealService:
    global _docuseal_service
    if _docuseal_service is None:
        _docuseal_service = DocuSealService()
    return _docuseal_service


def get_email_service() -> AzureEmailService:
    global _email_service
    if _email_service is None:
        _email_service = AzureEmailService()
    return _email_service


def resolve_backend_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


def _resolve_contract_filepath(contract_id: str, db: Session) -> Path:
    """Resolve the contract file path, trying multiple strategies."""
    output_dir = resolve_backend_path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Strategy 1: Get path from DB and check if file exists at that exact location
    latest_ver = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract_id)
        .order_by(ContractVersionDB.version_number.desc())
        .first()
    )

    if latest_ver and latest_ver.file_path:
        stored = Path(latest_ver.file_path)

        # Try the stored path directly
        if stored.exists():
            logger.info("Found contract file at stored path: %s", stored)
            return stored

        # Strategy 2: Try the filename from stored path in current output_dir
        filename = stored.name
        candidate = output_dir / filename
        if candidate.exists():
            logger.info("Found contract file at reconstructed path: %s", candidate)
            return candidate

    # Strategy 3: Convention-based path
    fallback = output_dir / f"contrato_{contract_id}.docx"
    if fallback.exists():
        logger.info("Found contract file at fallback path: %s", fallback)
        return fallback

    # Log what was tried for debugging
    logger.error(
        "Contract file not found for %s. Tried: stored=%s, output_dir=%s",
        contract_id,
        latest_ver.file_path if latest_ver else "N/A",
        output_dir,
    )
    raise HTTPException(status_code=404, detail="Contract file not found")


@router.post("/send-for-signature", response_model=DocuSealResponse)
async def send_for_signature(
    data: DocuSealRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocuSealResponse:
    """Send contract for digital signature via DocuSeal."""
    try:
        service = get_docuseal_service()

        filepath = _resolve_contract_filepath(data.contract_id, db)

        latest_ver = (
            db.query(ContractVersionDB)
            .filter(ContractVersionDB.contract_id == data.contract_id)
            .order_by(ContractVersionDB.version_number.desc())
            .first()
        )

        # Check if the DOCX contains DocuSeal field tags; if not, regenerate it
        needs_regen = True
        try:
            with open(filepath, "rb") as f:
                content_bytes = f.read()
            if b"{{" in content_bytes and b"|signature|" in content_bytes:
                needs_regen = False
        except Exception:
            pass

        if needs_regen and latest_ver and latest_ver.form_data_json:
            # Regenerate the DOCX with DocuSeal tags
            import json as _json
            from app.models.contract import ContratoRequest as _CR
            from app.services.contract_generator import ContractGenerator as _CG

            try:
                form_data = _json.loads(latest_ver.form_data_json)
                contrato_data = _CR(**form_data)
                gen = _CG()
                _, new_filepath = gen.generate(contrato_data, contract_id=data.contract_id)
                filepath = Path(new_filepath)
                # Update stored path
                latest_ver.file_path = str(filepath)
                db.commit()
                logger.info("Regenerated DOCX with DocuSeal tags for contract %s", data.contract_id)
            except Exception as regen_err:
                logger.warning("Failed to regenerate DOCX: %s", regen_err)

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

        # Send for signature — add C&F (Contratado) and the lawyer (Advogado) alongside the client
        all_signatarios = list(data.signatarios)

        # Always include C&F as "Contratado" role (the firm)
        cf_already_included = any(s.get("role") == "Contratado" for s in all_signatarios)
        if not cf_already_included:
            all_signatarios.append({
                "email": settings.cf_signer_email,
                "name": "Carvalho & Furtado Advogados",
                "role": "Contratado",
            })

        # Always include the logged-in lawyer as "Advogado" role
        if user.email:
            # Check if the logged-in user is already in the list
            user_already_included = any(s.get("email") == user.email for s in all_signatarios)
            if not user_already_included:
                all_signatarios.append({
                    "email": user.email,
                    "name": user.name or user.email,
                    "role": "Advogado",
                })

        # Assign order for sequential signing:
        # Contratante(s) sign first, Advogado second, Contratado (C&F) last
        _ROLE_ORDER = {"Contratante": 1, "Advogado": 2, "Contratado": 3}
        for sig in all_signatarios:
            sig["order"] = _ROLE_ORDER.get(sig.get("role", "Contratante"), 1)

        sign_result = await service.send_for_signature(
            template_id=template_id,
            signatarios=all_signatarios,
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

            # Send copy of contract to financeiro
            await _send_contract_to_financeiro(data.contract_id, str(filepath), contract, db, user)

            # Send participação sheet to financeiro if available
            await _send_participacao_to_financeiro(data.contract_id, contract, latest_ver, db, user)

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


async def _send_contract_to_financeiro(
    contract_id: str,
    filepath: str,
    contract: ContractDB | None,
    db: Session,
    user: CurrentUser,
) -> None:
    """Send a copy of the contract to the financeiro email."""
    try:
        email_service = get_email_service()
        client_name = contract.client_name if contract else "Cliente"

        result = await email_service.send_email_with_attachment(
            to_email=settings.financeiro_email,
            to_name="Financeiro C&F",
            subject=f"Cópia Contrato de Honorários — {client_name}",
            attachment_path=filepath,
            attachment_name=f"contrato_honorarios_{contract_id}.docx",
        )

        if result.get("success"):
            logger.info("Contract copy sent to financeiro for contract %s", contract_id)
            if contract:
                db.add(AuditLogDB(
                    contract_id=contract_id,
                    action="envio_copia_financeiro",
                    detail=f"Cópia do contrato enviada para {settings.financeiro_email}",
                    version_number=contract.current_version,
                    user_email=user.email,
                    created_at=utcnow(),
                ))
                db.commit()
        else:
            logger.warning("Failed to send contract copy to financeiro: %s", result.get("error"))
    except Exception as e:
        logger.error("Error sending contract copy to financeiro: %s", e)


async def _send_participacao_to_financeiro(
    contract_id: str,
    contract: ContractDB | None,
    latest_ver: ContractVersionDB | None,
    db: Session,
    user: CurrentUser,
) -> None:
    """Send participação sheet to financeiro based on stored form data."""
    try:
        if not latest_ver or not latest_ver.form_data_json:
            return

        form_data = json.loads(latest_ver.form_data_json)
        participacao = form_data.get("participacao", {})

        if not participacao.get("tem_participacao"):
            return

        client_name = contract.client_name if contract else "Cliente"

        rows = []
        if participacao.get("percentual_ou_valor"):
            rows.append(("Percentual/Valor", participacao["percentual_ou_valor"]))
        if participacao.get("para_quem"):
            rows.append(("Para quem", participacao["para_quem"]))
        if participacao.get("natureza"):
            rows.append(("Natureza", participacao["natureza"]))
        if participacao.get("responsavel_captacao"):
            rows.append(("Resp. Captação", participacao["responsavel_captacao"]))
        if participacao.get("responsavel_gestao"):
            rows.append(("Resp. Gestão", participacao["responsavel_gestao"]))
        if participacao.get("contato_financeiro_cliente"):
            rows.append(("Contato Financeiro Cliente", participacao["contato_financeiro_cliente"]))

        if not rows:
            return

        table_rows = "".join(
            f'<tr><td style="padding:8px;border:1px solid #D7D1CA;font-weight:600;">{k}</td>'
            f'<td style="padding:8px;border:1px solid #D7D1CA;">{v}</td></tr>'
            for k, v in rows
        )

        html = (
            '<div style="font-family: Segoe UI, Tahoma, sans-serif; max-width: 600px;">'
            '<div style="background-color: #1A3C34; padding: 20px 28px; border-radius: 8px 8px 0 0;">'
            '<span style="color: #FFFFFF; font-size: 16px; font-weight: 500;">Ficha de Participação — Uso Interno</span>'
            '</div>'
            '<div style="padding: 24px; border: 1px solid #D7D1CA; border-top: none; border-radius: 0 0 8px 8px;">'
            f'<p><strong>Cliente:</strong> {client_name}</p>'
            f'<p><strong>Contrato:</strong> {contract_id}</p>'
            f'<p><strong>Registrado por:</strong> {user.email}</p>'
            f'<p><strong>Momento:</strong> Envio para assinatura digital</p>'
            '<table style="width:100%;border-collapse:collapse;margin-top:16px;">'
            f'{table_rows}'
            '</table>'
            '</div></div>'
        )

        email_service = get_email_service()
        result = await email_service.send_html_email(
            to_email=settings.financeiro_email,
            to_name="Financeiro C&F",
            subject=f"Ficha de Participação (Assinatura) — {client_name}",
            html_content=html,
        )

        if result.get("success"):
            logger.info("Participacao sheet sent to financeiro for contract %s", contract_id)
            if contract:
                db.add(AuditLogDB(
                    contract_id=contract_id,
                    action="envio_participacao_assinatura",
                    detail=f"Ficha de participação enviada para {settings.financeiro_email} (assinatura)",
                    version_number=contract.current_version,
                    user_email=user.email,
                    created_at=utcnow(),
                ))
                db.commit()
        else:
            logger.warning("Failed to send participacao to financeiro: %s", result.get("error"))
    except Exception as e:
        logger.error("Error sending participacao to financeiro: %s", e)


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
