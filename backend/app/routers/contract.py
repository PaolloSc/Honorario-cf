from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

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


@router.post("/generate", response_model=ContratoResponse)
async def generate_contract(data: ContratoRequest) -> ContratoResponse:
    """Generate a contract from form data."""
    try:
        gen = get_generator()
        contract_id, filepath = gen.generate(data)

        logger.info("Contract generated: %s -> %s", contract_id, filepath)

        return ContratoResponse(
            success=True,
            message="Contrato gerado com sucesso",
            contract_id=contract_id,
            download_url=f"/api/contract/{contract_id}/download",
        )
    except Exception as e:
        logger.error("Failed to generate contract: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{contract_id}/download")
async def download_contract(contract_id: str) -> FileResponse:
    """Download a generated contract file."""
    gen = get_generator()
    filepath = Path(gen.output_dir) / f"contrato_{contract_id}.docx"

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Contract not found")

    return FileResponse(
        path=str(filepath),
        filename=f"contrato_{contract_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )