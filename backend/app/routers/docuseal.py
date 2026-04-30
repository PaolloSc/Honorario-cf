from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import BACKEND_DIR, settings
from app.services.docuseal import DocuSealService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docuseal", tags=["DocuSeal"])


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
async def send_for_signature(data: DocuSealRequest) -> DocuSealResponse:
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
            return DocuSealResponse(
                success=True,
                message="Documento enviado para assinatura com sucesso",
                submission_id=submission.get("id"),
            )
        else:
            return DocuSealResponse(
                success=False,
                message=sign_result.get("message", "Erro ao enviar para assinatura"),
            )

    except Exception as e:
        logger.error("DocuSeal error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
