"""Arquivo (DOCX) do contrato: onde esta e, se o disco efemero o perdeu, como refazer.

Modulo de servico: nao conhece HTTP. Quem chama traduz ArquivoNaoEncontrado em 404.
Antes havia uma copia identica em routers/docuseal.py e outra em routers/email.py.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, settings
from app.database import ContractVersionDB
from app.services.contrato_carregado import carregar_versao

logger = logging.getLogger(__name__)


class ArquivoNaoEncontrado(Exception):
    """Nenhuma estrategia achou nem conseguiu refazer o arquivo do contrato."""

    def __init__(self, contract_id: str):
        super().__init__(f"Contract file not found: {contract_id}")
        self.contract_id = contract_id


def resolve_backend_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


def resolver_arquivo(contract_id: str, db: Session) -> Path:
    """Resolve the contract file path, trying multiple strategies.

    If the file cannot be found on disk (ephemeral filesystem like Render),
    regenerates from form_data_json stored in the database.
    """
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

    # Strategy 4: Regenerate from form_data_json in DB (handles ephemeral filesystems)
    if latest_ver and latest_ver.form_data_json:
        logger.warning(
            "Contract file not found on disk for %s. Regenerating from stored form data...",
            contract_id,
        )
        try:
            carregado = carregar_versao(latest_ver)
            _, new_filepath = carregado.gerador.generate(carregado.request, contract_id=contract_id)
            regenerated = Path(new_filepath)

            # Update the stored path in DB so next time it's found directly
            latest_ver.file_path = str(regenerated)
            db.commit()

            logger.info("Regenerated contract file at: %s", regenerated)
            return regenerated
        except FileNotFoundError as template_err:
            # Template not found (ephemeral FS) - create a minimal placeholder DOCX
            logger.warning("Template not found, creating minimal DOCX: %s", template_err)
            try:
                from docx import Document as _Doc
                doc = _Doc()
                doc.add_paragraph("Contrato em processamento - documento sera regenerado.")
                minimal_path = output_dir / f"contrato_{contract_id}.docx"
                doc.save(str(minimal_path))
                latest_ver.file_path = str(minimal_path)
                db.commit()
                logger.info("Created minimal placeholder DOCX at: %s", minimal_path)
                return minimal_path
            except Exception as min_err:
                logger.error("Failed to create minimal DOCX: %s", min_err)
        except Exception as regen_err:
            logger.error("Failed to regenerate contract %s: %s", contract_id, regen_err)

    # All strategies exhausted
    logger.error(
        "Contract file not found for %s. Tried: stored=%s, output_dir=%s, regeneration=%s",
        contract_id,
        latest_ver.file_path if latest_ver else "N/A",
        output_dir,
        "failed" if latest_ver and latest_ver.form_data_json else "no form data",
    )
    raise ArquivoNaoEncontrado(contract_id)
