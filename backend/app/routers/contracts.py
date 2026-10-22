from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
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
from app.models.documentos_complementares import (
    REQUESTS as REQUESTS_COMPLEMENTARES,
    email_contato,
    nome_exibicao,
)
from app.models.contract import ContratoRequest
from app.services.contract_dispatch import parse_form_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contracts", tags=["Contracts Management"])

# ── Response schemas ──────────────────────────────────────────────

class ContractSummary(BaseModel):
    contract_id: str
    status: str
    client_name: str
    client_email: str
    tipo_contrato: str
    contrato_origem_id: Optional[str] = None
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
    tipo_contrato: str = "honorarios"
    contrato_origem_id: Optional[str] = None
    # Socio pre-selecionado para assinar pelo escritorio (ver socio_sugerido)
    socio_sugerido: Optional[str] = None
    versions: list[VersionSummary]
    audit_log: list[AuditEntry]


class ContractFormDataResponse(BaseModel):
    contract_id: str
    version_number: int
    form_data: dict


class UpdateContractRequest(BaseModel):
    form_data: dict
    version: Optional[int] = None  # versao que a tela carregou; diferente da atual = aba desatualizada


# ── Helpers ───────────────────────────────────────────────────────

def _travado(contract: ContractDB, db: Session) -> bool:
    """Enviado para assinatura ou assinado AGORA: nao se grava por cima.

    So o estado atual conta: 'Cancelar envio' arquiva a submissao e volta a rascunho.
    """
    return contract.status in ("enviado", "assinado")


def _exigir_editavel(contract: ContractDB, db: Session) -> None:
    if not _travado(contract, db):
        return
    assinado = contract.status == "assinado"
    raise HTTPException(409, {
        "codigo": "contrato_travado",
        "motivo": "Este contrato já foi assinado e não pode ser alterado." if assinado
        else "Este contrato já foi enviado para assinatura e não pode ser alterado.",
        "sugestao": "Crie um novo substabelecimento com os dados corretos." if contract.tipo_contrato == "substabelecimento"
        else "Crie um aditivo para mudar o que foi assinado." if assinado
        else "Use \"Cancelar envio para assinatura\" na página do contrato para voltar a editar.",
    })


def _exigir_versao_atual(contract: ContractDB, versao: int | None) -> None:
    if versao is not None and versao != contract.current_version:
        raise HTTPException(409, {
            "codigo": "versao_desatualizada",
            "motivo": f"Este contrato foi alterado por outra pessoa ou aba (você abriu a versão {versao}; a atual é a {contract.current_version}).",
            "versao_atual": contract.current_version,
        })


def _arquivo_da_versao(filepath: str | Path, contract_id: str, versao: int) -> str:
    """Copia o DOCX para um nome proprio da versao (o gerador reaproveita sempre o mesmo nome)."""
    origem = Path(filepath)
    destino = origem.with_name(f"contrato_{contract_id}_v{versao}.docx")
    if origem != destino:
        shutil.copyfile(origem, destino)
    return str(destino)


def _congelar_versao_atual(db: Session, contract: ContractDB) -> None:
    """Antes de gerar a proxima versao, prende o DOCX da atual a um nome proprio."""
    ver = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract.contract_id, ContractVersionDB.version_number == contract.current_version)
        .first()
    )
    if ver and ver.file_path and Path(ver.file_path).exists():
        ver.file_path = _arquivo_da_versao(ver.file_path, contract.contract_id, ver.version_number)


def _validar_valores_do_honorario(form_data: dict, contrato_data) -> None:
    """Regras de valor do ContratoRequest (exito 0-100, hora/pro-labore/mensalidade > 0).

    parse_form_data usa o contexto 'previa' (aceita dado antigo ao regerar/baixar); editar e'
    gravar dado novo, entao aqui vale a regra completa, com 422 por campo como no wizard.
    """
    if not isinstance(contrato_data, ContratoRequest):
        return
    try:
        ContratoRequest.model_validate(form_data)
    except ValidationError as e:
        raise RequestValidationError([
            {**err, "loc": ("body", "form_data", *err["loc"])} for err in e.errors(include_context=False, include_url=False)
        ])


def _atualizar_documentos_do_cliente(db: Session, contract: ContractDB, form_data: dict, contrato_data, user: CurrentUser) -> None:
    """Mantem a busca por CPF/CNPJ e a ficha de participacao (rascunho) iguais ao contrato salvo."""
    contract.cliente_docs = serialize_cliente_docs(form_data)
    if contract.tipo_contrato in REQUESTS_COMPLEMENTARES or not hasattr(contrato_data, "participacao"):
        return
    from app.routers.contract import campos_rascunho_participacao

    try:
        campos = campos_rascunho_participacao(contrato_data, user.email, user.name)
    except Exception as e:  # nao bloqueia a edicao
        logger.warning("Falha ao atualizar ficha de participacao de %s: %s", contract.contract_id, e)
        return
    # So o que vem do contrato (cliente e tipo de honorario): percentuais, e-mail e observacoes
    # que o financeiro complementou no rascunho ficam como estao.
    do_contrato = {k: campos[k] for k in ("cliente_cpf_cnpj", "tipo_honorario")}
    for ficha in db.query(ParticipacaoDB).filter(
        ParticipacaoDB.contract_id == contract.contract_id, ParticipacaoDB.aprovada.is_(False)
    ):
        for k, v in do_contrato.items():
            setattr(ficha, k, v)


def _extract_client_info(data: dict) -> tuple[str, str]:
    tipo = data.get("tipo_contrato")
    if tipo in REQUESTS_COMPLEMENTARES:
        # Aditivo/distrato guardam os contratantes; o substabelecimento, o outorgante.
        parsed = REQUESTS_COMPLEMENTARES[tipo](**data)
        return (nome_exibicao(parsed), email_contato(parsed))
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
                tipo_contrato=c.tipo_contrato,
                contrato_origem_id=c.contrato_origem_id,
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

    from app.routers.docuseal import socio_sugerido

    atual = next((v for v in contract.versions if v.version_number == contract.current_version), None)
    sugerido = socio_sugerido(atual.form_data_json if atual else None, db)

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
        tipo_contrato=contract.tipo_contrato or "honorarios",
        contrato_origem_id=contract.contrato_origem_id,
        socio_sugerido=sugerido.email if sugerido else None,
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


class DocumentoDerivado(BaseModel):
    contract_id: str
    tipo_contrato: str
    status: str
    client_name: str
    created_at: str


@router.get("/{contract_id}/documentos")
def list_documentos(
    contract_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Aditivos, distrato e substabelecimentos derivados do contrato."""
    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(404, "Contrato nao encontrado")
    _check_access(contract, user)

    query = db.query(ContractDB).filter(ContractDB.contrato_origem_id == contract_id)
    if user.role != "admin":  # mesma regra da lista de contratos
        query = query.filter(ContractDB.created_by == user.email)
    return {
        "documentos": [
            DocumentoDerivado(
                contract_id=d.contract_id,
                tipo_contrato=d.tipo_contrato,
                status=d.status,
                client_name=d.client_name,
                created_at=d.created_at.isoformat(),
            )
            for d in query.order_by(ContractDB.created_at, ContractDB.id).all()
        ]
    }


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
    _exigir_versao_atual(contract, body.version)
    _exigir_editavel(contract, db)

    if contract.tipo_contrato in REQUESTS_COMPLEMENTARES:
        # O vinculo e' a coluna; o form_data nao pode divergir dela.
        body.form_data["contrato_origem_id"] = contract.contrato_origem_id

    try:
        contrato_data, gen = parse_form_data(body.form_data, estrito=True)
    except Exception as e:
        raise HTTPException(422, f"Dados invalidos: {e}")
    _validar_valores_do_honorario(body.form_data, contrato_data)

    _congelar_versao_atual(db, contract)
    _, filepath = gen.generate(contrato_data, contract_id=contract_id)

    new_version = contract.current_version + 1
    filepath = _arquivo_da_versao(filepath, contract_id, new_version)
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
    _atualizar_documentos_do_cliente(db, contract, body.form_data, contrato_data, user)

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
    if old_status == "assinado" and status != "assinado":
        raise HTTPException(409, "Contrato assinado não muda de status. Para alterar algo, crie um aditivo.")
    if old_status == "enviado" and status in ("rascunho", "cancelado"):
        raise HTTPException(409, "Para sair de \"enviado\" use \"Cancelar envio para assinatura\" (arquiva o link no DocuSeal).")
    fora_do_sistema = status == "assinado" and old_status != "enviado"
    if status == "enviado" and old_status != "enviado":
        enviado_pelo_docuseal = (
            db.query(ContractVersionDB)
            .filter(ContractVersionDB.contract_id == contract_id, ContractVersionDB.docuseal_submission_id.isnot(None))
            .first()
        )
        if not enviado_pelo_docuseal:
            raise HTTPException(409, "Este contrato não foi enviado para assinatura pelo sistema; use o envio pelo DocuSeal.")
    contract.status = status
    contract.updated_by = user.email
    contract.updated_at = utcnow()

    detalhe = f"{old_status} -> {status}"
    if fora_do_sistema:  # assinado em papel ou fora do DocuSeal: fica registrado quem marcou e quando
        detalhe += f" (assinado fora do sistema, marcado por {user.email})"
    _log_action(db, contract_id, "mudanca_status", detalhe, user_email=user.email)

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
    _exigir_editavel(contract, db)

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
        contrato_data, gen = parse_form_data(form_data)
    except Exception as e:
        raise HTTPException(422, f"Dados da versao {version} invalidos: {e}")

    _congelar_versao_atual(db, contract)
    _, filepath = gen.generate(contrato_data, contract_id=contract_id)

    # Create a new version based on the old data
    new_version = contract.current_version + 1
    filepath = _arquivo_da_versao(filepath, contract_id, new_version)
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
    _atualizar_documentos_do_cliente(db, contract, form_data, contrato_data, user)

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
