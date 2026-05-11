from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import (
    AuditLogDB,
    ContractDB,
    ContractVersionDB,
    get_db,
    utcnow,
)
from app.models.contract import ContratoRequest
from app.services.contract_generator import ContractGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contracts", tags=["Contracts Management"])

_generator: ContractGenerator | None = None


def _gen() -> ContractGenerator:
    global _generator
    if _generator is None:
        _generator = ContractGenerator()
    return _generator


# ── Response schemas ──────────────────────────────────────────────

class ContractSummary(BaseModel):
    contract_id: str
    status: str
    client_name: str
    client_email: str
    current_version: int
    created_by: Optional[str] = None
    created_at: str
    updated_at: str


class ContractListResponse(BaseModel):
    contracts: list[ContractSummary]
    total: int
    page: int
    page_size: int


class VersionSummary(BaseModel):
    version_number: int
    file_path: Optional[str] = None
    docuseal_submission_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str


class AuditEntry(BaseModel):
    action: str
    detail: Optional[str] = None
    version_number: Optional[int] = None
    user_email: Optional[str] = None
    created_at: str


class ContractDetail(BaseModel):
    contract_id: str
    status: str
    client_name: str
    client_email: str
    current_version: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: str
    updated_at: str
    versions: list[VersionSummary]
    audit_log: list[AuditEntry]


class ContractFormDataResponse(BaseModel):
    contract_id: str
    version_number: int
    form_data: dict


class UpdateContractRequest(BaseModel):
    form_data: dict


# ── Helpers ───────────────────────────────────────────────────────

def _extract_client_info(data: dict) -> tuple[str, str]:
    contratantes = data.get("contratantes", [])
    if not contratantes:
        return ("", "")
    first = contratantes[0]
    name = first.get("nome") or first.get("razao_social") or ""
    email = first.get("email", "")
    return (name, email)


def _log_action(
    db: Session,
    contract_id: str,
    action: str,
    detail: str = "",
    version: int | None = None,
    user_email: str = "",
):
    entry = AuditLogDB(
        contract_id=contract_id,
        action=action,
        detail=detail,
        version_number=version,
        user_email=user_email,
        created_at=utcnow(),
    )
    db.add(entry)


def _check_access(contract: ContractDB, user: CurrentUser):
    if user.role == "admin":
        return
    if contract.created_by != user.email:
        raise HTTPException(403, "Sem permissao para acessar este contrato")


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("", response_model=ContractListResponse)
def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ContractDB)

    # Advogado ve apenas seus contratos; admin ve todos
    if user.role != "admin":
        query = query.filter(ContractDB.created_by == user.email)

    if status:
        query = query.filter(ContractDB.status == status)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (ContractDB.client_name.ilike(pattern))
            | (ContractDB.client_email.ilike(pattern))
            | (ContractDB.contract_id.ilike(pattern))
        )

    total = query.count()
    contracts = (
        query.order_by(ContractDB.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ContractListResponse(
        contracts=[
            ContractSummary(
                contract_id=c.contract_id,
                status=c.status,
                client_name=c.client_name,
                client_email=c.client_email,
                current_version=c.current_version,
                created_by=c.created_by,
                created_at=c.created_at.isoformat(),
                updated_at=c.updated_at.isoformat(),
            )
            for c in contracts
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{contract_id}", response_model=ContractDetail)
def get_contract(
    contract_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(404, "Contrato nao encontrado")

    _check_access(contract, user)

    return ContractDetail(
        contract_id=contract.contract_id,
        status=contract.status,
        client_name=contract.client_name,
        client_email=contract.client_email,
        current_version=contract.current_version,
        created_by=contract.created_by,
        updated_by=contract.updated_by,
        created_at=contract.created_at.isoformat(),
        updated_at=contract.updated_at.isoformat(),
        versions=[
            VersionSummary(
                version_number=v.version_number,
                file_path=v.file_path,
                docuseal_submission_id=v.docuseal_submission_id,
                created_by=v.created_by,
                created_at=v.created_at.isoformat(),
            )
            for v in contract.versions
        ],
        audit_log=[
            AuditEntry(
                action=a.action,
                detail=a.detail,
                version_number=a.version_number,
                user_email=a.user_email,
                created_at=a.created_at.isoformat(),
            )
            for a in contract.audit_logs
        ],
    )


@router.get("/{contract_id}/form-data", response_model=ContractFormDataResponse)
def get_contract_form_data(
    contract_id: str,
    version: Optional[int] = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(404, "Contrato nao encontrado")

    _check_access(contract, user)

    query = db.query(ContractVersionDB).filter(ContractVersionDB.contract_id == contract_id)
    if version:
        ver = query.filter(ContractVersionDB.version_number == version).first()
    else:
        ver = query.order_by(ContractVersionDB.version_number.desc()).first()

    if not ver:
        raise HTTPException(404, "Versao nao encontrada")

    return ContractFormDataResponse(
        contract_id=contract_id,
        version_number=ver.version_number,
        form_data=json.loads(ver.form_data_json),
    )


@router.put("/{contract_id}", response_model=dict)
def update_contract(
    contract_id: str,
    body: UpdateContractRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(404, "Contrato nao encontrado")

    _check_access(contract, user)

    try:
        contrato_data = ContratoRequest(**body.form_data)
    except Exception as e:
        raise HTTPException(422, f"Dados invalidos: {e}")

    gen = _gen()
    _, filepath = gen.generate(contrato_data, contract_id=contract_id)

    new_version = contract.current_version + 1
    client_name, client_email = _extract_client_info(body.form_data)

    version_entry = ContractVersionDB(
        contract_id=contract_id,
        version_number=new_version,
        form_data_json=json.dumps(body.form_data, ensure_ascii=False),
        file_path=str(filepath),
        created_by=user.email,
        created_at=utcnow(),
    )
    db.add(version_entry)

    contract.current_version = new_version
    contract.client_name = client_name
    contract.client_email = client_email
    contract.status = "rascunho"
    contract.updated_by = user.email
    contract.updated_at = utcnow()

    _log_action(db, contract_id, "edicao", f"Nova versao {new_version} gerada por {user.name}", new_version, user.email)

    db.commit()

    return {
        "success": True,
        "message": f"Contrato atualizado (versao {new_version})",
        "contract_id": contract_id,
        "version": new_version,
        "download_url": f"/api/contract/{contract_id}/download",
    }


@router.patch("/{contract_id}/status")
def update_contract_status(
    contract_id: str,
    status: str = Query(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(404, "Contrato nao encontrado")

    _check_access(contract, user)

    valid_statuses = {"rascunho", "enviado", "assinado", "cancelado"}
    if status not in valid_statuses:
        raise HTTPException(422, f"Status invalido. Validos: {valid_statuses}")

    old_status = contract.status
    contract.status = status
    contract.updated_by = user.email
    contract.updated_at = utcnow()

    _log_action(db, contract_id, "mudanca_status", f"{old_status} -> {status}", user_email=user.email)

    db.commit()
    return {"success": True, "status": status}



@router.post("/{contract_id}/rollback")
def rollback_contract(
    contract_id: str,
    version: int = Query(..., ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rollback a contract to a previous version, regenerating the DOCX from stored form data."""
    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(404, "Contrato nao encontrado")

    _check_access(contract, user)

    # Find the target version
    target_ver = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract_id, ContractVersionDB.version_number == version)
        .first()
    )
    if not target_ver:
        raise HTTPException(404, f"Versao {version} nao encontrada")

    if version == contract.current_version:
        raise HTTPException(422, "Contrato ja esta nesta versao")

    # Regenerate the DOCX from stored form data
    try:
        form_data = json.loads(target_ver.form_data_json)
        contrato_data = ContratoRequest(**form_data)
    except Exception as e:
        raise HTTPException(422, f"Dados da versao {version} invalidos: {e}")

    gen = _gen()
    _, filepath = gen.generate(contrato_data, contract_id=contract_id)

    # Create a new version based on the old data
    new_version = contract.current_version + 1
    client_name, client_email = _extract_client_info(form_data)

    version_entry = ContractVersionDB(
        contract_id=contract_id,
        version_number=new_version,
        form_data_json=target_ver.form_data_json,
        file_path=str(filepath),
        created_by=user.email,
        created_at=utcnow(),
    )
    db.add(version_entry)

    contract.current_version = new_version
    contract.client_name = client_name
    contract.client_email = client_email
    contract.status = "rascunho"
    contract.updated_by = user.email
    contract.updated_at = utcnow()

    _log_action(
        db, contract_id, "rollback",
        f"Revertido para versao {version} (nova versao {new_version}) por {user.email}",
        new_version, user.email,
    )

    db.commit()

    return {
        "success": True,
        "message": f"Contrato revertido para versao {version} (nova versao {new_version})",
        "contract_id": contract_id,
        "version": new_version,
    }
