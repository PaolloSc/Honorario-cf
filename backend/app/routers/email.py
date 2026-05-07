from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, settings
from app.database import AuditLogDB, ContractDB, get_db, utcnow
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


@router.post("/send", response_model=EmailResponse)
async def send_contract_email(data: EmailRequest, db: Session = Depends(get_db)) -> EmailResponse:
    """Send contract via email using Azure Communication Services."""
    try:
        # Find the contract file
        filepath = resolve_backend_path(settings.output_dir) / f"contrato_{data.contract_id}.docx"

        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Contract file not found")

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
