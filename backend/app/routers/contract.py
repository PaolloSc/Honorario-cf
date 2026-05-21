from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import (
    AuditLogDB,
    ContractDB,
    ContractVersionDB,
    ParticipacaoDB,
    get_db,
    serialize_cliente_docs,
    utcnow,
)
from app.models.contract import ContratoRequest, ContratoResponse
from app.services.contract_generator import ContractGenerator


def _infer_tipo_honorario(data: ContratoRequest) -> str:
    """Olha todos escopos. Se >1 tipo distinto → 'misto'; senão usa o único; default 'mensalidade'."""
    tipos = set()
    for esc in data.escopos:
        for h in esc.honorarios:
            v = h.value if hasattr(h, "value") else str(h)
            # Mapeia para vocabulário do calculator
            if v == "hora_trabalhada":
                tipos.add("hora")
            elif v == "pro_labore":
                tipos.add("prolabore")
            elif v == "mensalidade":
                # Verifica subtipo advocacia_partido
                m = esc.mensalidade
                if m and getattr(m, "subtipo", None) and m.subtipo.value == "advocacia_partido":
                    tipos.add("partido")
                else:
                    tipos.add("mensalidade")
            elif v == "exito":
                tipos.add("exito")
            elif v == "permuta":
                tipos.add("exito")  # permuta segue regra de êxito (sem limite)
    if not tipos:
        return "mensalidade"
    if len(tipos) > 1:
        return "misto"
    return next(iter(tipos))


def _extract_cpf_cnpj(data: ContratoRequest) -> str | None:
    if not data.contratantes:
        return None
    first = data.contratantes[0]
    return getattr(first, "cpf", None) or getattr(first, "cnpj", None)

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
def generate_contract(
    data: ContratoRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContratoResponse:
    try:
        gen = get_generator()
        contract_id, filepath = gen.generate(data)

        client_name, client_email = _extract_client_info(data)
        form_dict = data.model_dump(mode="json")

        contract = ContractDB(
            contract_id=contract_id,
            status="rascunho",
            client_name=client_name,
            client_email=client_email,
            current_version=1,
            created_by=user.email,
            updated_by=user.email,
            created_at=utcnow(),
            updated_at=utcnow(),
            cliente_docs=serialize_cliente_docs(form_dict),
        )
        db.add(contract)

        form_data_json = json.dumps(form_dict, ensure_ascii=False)
        version = ContractVersionDB(
            contract_id=contract_id,
            version_number=1,
            form_data_json=form_data_json,
            file_path=filepath,
            created_by=user.email,
            created_at=utcnow(),
        )
        db.add(version)

        audit = AuditLogDB(
            contract_id=contract_id,
            action="criacao",
            detail=f"Contrato gerado para {client_name}",
            version_number=1,
            user_email=user.email,
            created_at=utcnow(),
        )
        db.add(audit)

        # ── Plano A: cria Participação rascunho automática para o financeiro ──
        # Percentuais zerados + aprovada=False. Setor financeiro complementa e aprova.
        try:
            tipo = _infer_tipo_honorario(data)
            participacao_data = data.participacao
            beneficiario_email = (
                participacao_data.para_quem
                if participacao_data and participacao_data.tem_participacao and participacao_data.para_quem
                else user.email
            )
            beneficiario_nome = (
                participacao_data.responsavel_captacao
                if participacao_data and participacao_data.responsavel_captacao
                else user.name
            )
            natureza_val = (
                participacao_data.natureza
                if participacao_data and participacao_data.natureza in ("contratual", "societario")
                else "contratual"
            )
            rascunho = ParticipacaoDB(
                contract_id=contract_id,
                beneficiario_email=beneficiario_email or user.email,
                beneficiario_nome=beneficiario_nome or "",
                tipo_honorario=tipo,
                percentual_captacao=0.0,
                percentual_performance=0.0,
                natureza=natureza_val,
                cliente_cpf_cnpj=_extract_cpf_cnpj(data),
                data_inicio=utcnow().date(),
                vinculo_ativo=True,
                aprovada=False,
                observacoes=(
                    f"Rascunho gerado automaticamente pelo wizard. "
                    f"Captação responsável: {participacao_data.responsavel_captacao or '—'} · "
                    f"Gestão: {participacao_data.responsavel_gestao or '—'}"
                    if participacao_data
                    else "Rascunho gerado automaticamente pelo wizard."
                ),
                created_by=user.email,
                created_at=utcnow(),
            )
            db.add(rascunho)
            db.add(
                AuditLogDB(
                    contract_id=contract_id,
                    action="participacao_rascunho",
                    detail=f"Rascunho automático criado para revisão do financeiro (tipo={tipo})",
                    user_email=user.email,
                    created_at=utcnow(),
                )
            )
        except Exception as part_err:
            # Não bloqueia geração de contrato se falhar criação do rascunho
            logger.warning("Falha ao criar participação rascunho automática: %s", part_err)

        db.commit()

        logger.info("Contract generated by %s: %s", user.email, contract_id)

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
def download_contract(
    contract_id: str,
    version: int | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        uuid.UUID(contract_id)
    except ValueError:
        raise HTTPException(400, "ID de contrato inválido")

    # Check ownership or admin
    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(404, "Contrato nao encontrado")
    if user.role != "admin" and contract.created_by != user.email:
        raise HTTPException(403, "Sem permissao")

    # Find the file path from DB (specific version or latest)
    query = db.query(ContractVersionDB).filter(ContractVersionDB.contract_id == contract_id)
    if version:
        ver = query.filter(ContractVersionDB.version_number == version).first()
    else:
        ver = query.order_by(ContractVersionDB.version_number.desc()).first()

    gen = get_generator()
    output_dir = Path(gen.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath: Path | None = None

    if ver and ver.file_path:
        stored = Path(ver.file_path)
        if stored.exists():
            filepath = stored
        else:
            candidate = output_dir / stored.name
            if candidate.exists():
                filepath = candidate

    if filepath is None:
        fallback = output_dir / f"contrato_{contract_id}.docx"
        if fallback.exists():
            filepath = fallback

    # Strategy 4: Regenerate from form_data_json (handles ephemeral filesystems)
    if filepath is None and ver and ver.form_data_json:
        logger.warning(
            "Contract file not on disk for %s. Regenerating from stored form data...",
            contract_id,
        )
        try:
            form_data = json.loads(ver.form_data_json)
            contrato_data = ContratoRequest(**form_data)
            _, new_filepath = gen.generate(contrato_data, contract_id=contract_id)
            filepath = Path(new_filepath)
            # Update stored path
            ver.file_path = str(filepath)
            db.commit()
            logger.info("Regenerated contract file at: %s", filepath)
        except FileNotFoundError as template_err:
            # Template not found (ephemeral FS) - create a minimal placeholder DOCX
            logger.warning("Template not found, creating minimal DOCX: %s", template_err)
            try:
                from docx import Document as _Doc
                doc = _Doc()
                doc.add_paragraph("Contrato em processamento - documento sera regenerado.")
                minimal_path = output_dir / f"contrato_{contract_id}.docx"
                doc.save(str(minimal_path))
                ver.file_path = str(minimal_path)
                db.commit()
                filepath = minimal_path
                logger.info("Created minimal placeholder DOCX at: %s", minimal_path)
            except Exception as min_err:
                logger.error("Failed to create minimal DOCX: %s", min_err)
        except Exception as regen_err:
            logger.error("Failed to regenerate contract %s: %s", contract_id, regen_err)

    if filepath is None or not filepath.exists():
        logger.error(
            "Contract file not found for %s. Tried: stored=%s, output_dir=%s",
            contract_id,
            ver.file_path if ver else "N/A",
            output_dir,
        )
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    return FileResponse(
        path=str(filepath),
        filename=f"contrato_{contract_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
