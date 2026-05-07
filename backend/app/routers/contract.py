from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import (
    AuditLogDB,
    ContractDB,
    ContractVersionDB,
    get_db,
    utcnow,
)
from app.models.contract import ContratoRequest, ContratoResponse
from app.services.contract_generator import ContractGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contract", tags=["Contract"])

_generator: ContractGenerator | None = None


def get_generator() -> ContractGenerator:
    global _generator
    if _generator is None:
        _generator = ContractGenerator()
    return _generator


def _extract_client_info(data: ContratoRequest) -> tuple[str, str]:
    if not data.contratantes:
        return ("", "")
    first = data.contratantes[0]
    name = getattr(first, "nome", None) or getattr(first, "razao_social", "")
    email = getattr(first, "email", "")
    return (name, email)


@router.post("/generate", response_model=ContratoResponse)
def generate_contract(data: ContratoRequest, db: Session = Depends(get_db)) -> ContratoResponse:
    try:
        gen = get_generator()
        contract_id, filepath = gen.generate(data)

        client_name, client_email = _extract_client_info(data)

        contract = ContractDB(
            contract_id=contract_id,
            status="rascunho",
            client_name=client_name,
            client_email=client_email,
            current_version=1,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(contract)

        form_data_json = json.dumps(data.model_dump(mode="json"), ensure_ascii=False)
        version = ContractVersionDB(
            contract_id=contract_id,
            version_number=1,
            form_data_json=form_data_json,
            file_path=filepath,
            created_at=utcnow(),
        )
        db.add(version)

        audit = AuditLogDB(
            contract_id=contract_id,
            action="criacao",
            detail=f"Contrato gerado para {client_name}",
            version_number=1,
            created_at=utcnow(),
        )
        db.add(audit)

        db.commit()

        logger.info("Contract generated and saved: %s -> %s", contract_id, filepath)

        return ContratoResponse(
            success=True,
            message="Contrato gerado com sucesso",
            contract_id=contract_id,
            download_url=f"/api/contract/{contract_id}/download",
        )
    except Exception as e:
        db.rollback()
        logger.error("Failed to generate contract: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{contract_id}/download")
async def download_contract(contract_id: str) -> FileResponse:
    gen = get_generator()
    filepath = Path(gen.output_dir) / f"contrato_{contract_id}.docx"

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Contract not found")

    return FileResponse(
        path=str(filepath),
        filename=f"contrato_{contract_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
