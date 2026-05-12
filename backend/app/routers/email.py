from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.config import BACKEND_DIR, settings
from app.database import AuditLogDB, ContractDB, ContractVersionDB, get_db, utcnow
from app.services.azure_email import AzureEmailService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["Email"])


class EmailRequest(BaseModel):
    contract_id: str
    destinatario_email: str
    destinatario_nome: str
    assunto: str = "Contrato de Honorários - C&F Advogados"


class EmailResponse(BaseModel):
    success: bool
    message: str


class ParticipacaoEmailRequest(BaseModel):
    contract_id: str
    cliente_nome: str
    percentual_ou_valor: str = ""
    para_quem: str = ""
    natureza: str = ""
    responsavel_captacao: str = ""
    responsavel_gestao: str = ""
    contato_financeiro_cliente: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, data):
        """Convert null/None values to empty strings for optional text fields."""
        if isinstance(data, dict):
            for field in ("percentual_ou_valor", "para_quem", "natureza",
                          "responsavel_captacao", "responsavel_gestao",
                          "contato_financeiro_cliente"):
                if data.get(field) is None:
                    data[field] = ""
        return data


_email_service: AzureEmailService | None = None


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


@router.post("/send", response_model=EmailResponse)
async def send_contract_email(
    data: EmailRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailResponse:
    """Send contract via email using Azure Communication Services."""
    try:
        filepath = _resolve_contract_filepath(data.contract_id, db)

        service = get_email_service()
        result = await service.send_email_with_attachment(
            to_email=data.destinatario_email,
            to_name=data.destinatario_nome,
            subject=data.assunto,
            attachment_path=str(filepath),
            attachment_name=f"contrato_honorarios_{data.contract_id}.docx",
        )

        if result["success"]:
            contract = db.query(ContractDB).filter(ContractDB.contract_id == data.contract_id).first()
            if contract:
                db.add(AuditLogDB(
                    contract_id=data.contract_id,
                    action="envio_email",
                    detail=f"E-mail enviado para {data.destinatario_email}",
                    version_number=contract.current_version,
                    user_email=user.email,
                    created_at=utcnow(),
                ))
                db.commit()
            return EmailResponse(success=True, message="E-mail enviado com sucesso")
        else:
            return EmailResponse(success=False, message=result.get("error", "Erro ao enviar e-mail"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-participacao", response_model=EmailResponse)
async def send_participacao_email(
    data: ParticipacaoEmailRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailResponse:
    """Send participation internal sheet to financeiro."""
    try:
        rows = []
        if data.percentual_ou_valor:
            rows.append(("Percentual/Valor", data.percentual_ou_valor))
        if data.para_quem:
            rows.append(("Para quem", data.para_quem))
        if data.natureza:
            rows.append(("Natureza", data.natureza))
        if data.responsavel_captacao:
            rows.append(("Resp. Captação", data.responsavel_captacao))
        if data.responsavel_gestao:
            rows.append(("Resp. Gestão", data.responsavel_gestao))
        if data.contato_financeiro_cliente:
            rows.append(("Contato Financeiro Cliente", data.contato_financeiro_cliente))

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
            f'<p><strong>Cliente:</strong> {data.cliente_nome}</p>'
            f'<p><strong>Contrato:</strong> {data.contract_id}</p>'
            f'<p><strong>Registrado por:</strong> {user.email}</p>'
            '<table style="width:100%;border-collapse:collapse;margin-top:16px;">'
            f'{table_rows}'
            '</table>'
            '</div></div>'
        )

        service = get_email_service()
        result = await service.send_html_email(
            to_email=settings.financeiro_email,
            to_name="Financeiro C&F",
            subject=f"Ficha de Participação — {data.cliente_nome}",
            html_content=html,
        )

        if result["success"]:
            contract = db.query(ContractDB).filter(ContractDB.contract_id == data.contract_id).first()
            if contract:
                db.add(AuditLogDB(
                    contract_id=data.contract_id,
                    action="envio_ficha_participacao",
                    detail=f"Ficha de participação enviada para {settings.financeiro_email}",
                    version_number=contract.current_version,
                    user_email=user.email,
                    created_at=utcnow(),
                ))
                db.commit()
            return EmailResponse(success=True, message="Ficha enviada para o financeiro")

        return EmailResponse(success=False, message=result.get("error", "Erro ao enviar ficha"))

    except Exception as e:
        logger.error("Failed to send participacao email: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
