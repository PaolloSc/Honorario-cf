from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.acesso import Capacidade, pode
from app.auth import CurrentUser, exigir_acesso_ao_contrato, get_current_user
from app.database import (
    ContractDB,
    ContractVersionDB,
    ParticipacaoDB,
    get_db,
    serialize_cliente_docs,
    utcnow,
)
from app.models.documentos_complementares import (
    REQUESTS as REQUESTS_COMPLEMENTARES,
    TIPO_DISTRATO,
)
from app.services.ciclo_contrato import (
    Arquivos,
    confirmar,
    gravar_versao,
    preparar_versao,
    registrar_auditoria,
    travado,
)
from app.services.contrato_carregado import carregar_versao, cliente_do_form_data, parse_form_data
from app.services.substabelecimento_vinculado import sincronizar_do_distrato
from app.utils.erros import MSG_ERRO_INTERNO

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

def _exigir_editavel(contract: ContractDB, db: Session) -> None:
    if not travado(contract):
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


def _atualizar_documentos_do_cliente(db: Session, contract: ContractDB, form_data: dict, contrato_data, user: CurrentUser) -> None:
    """Mantem a busca por CPF/CNPJ e a ficha de participacao (rascunho) iguais ao contrato salvo."""
    contract.cliente_docs = serialize_cliente_docs(form_data)
    if contract.tipo_contrato in REQUESTS_COMPLEMENTARES or not hasattr(contrato_data, "participacao"):
        return
    from app.services.rascunho_participacao import campos_rascunho_participacao

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
    if not pode(user, Capacidade.VER_CONTRATOS_DE_TODOS):
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

    exigir_acesso_ao_contrato(contract, user)

    from app.services.assinatura import socio_sugerido

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
    exigir_acesso_ao_contrato(contract, user)

    query = db.query(ContractDB).filter(ContractDB.contrato_origem_id == contract_id)
    if not pode(user, Capacidade.VER_CONTRATOS_DE_TODOS):  # mesma regra da lista de contratos
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

    exigir_acesso_ao_contrato(contract, user)

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

    exigir_acesso_ao_contrato(contract, user)
    _exigir_versao_atual(contract, body.version)
    _exigir_editavel(contract, db)

    if contract.tipo_contrato in REQUESTS_COMPLEMENTARES:
        # O vinculo e' a coluna; o form_data nao pode divergir dela.
        body.form_data["contrato_origem_id"] = contract.contrato_origem_id

    try:
        contrato_data, gen = parse_form_data(body.form_data, estrito=True)
    except ValidationError as e:
        # 422 por campo, como no wizard (a restauracao de versao segue no modo brando).
        raise RequestValidationError([
            {**err, "loc": ("body", "form_data", *err["loc"])} for err in e.errors(include_context=False, include_url=False)
        ])
    except Exception:
        # O texto da excecao pode trazer os dados digitados (CPF, nome): so' no log.
        logger.exception("Dados invalidos na edicao de %s", contract_id)
        raise HTTPException(422, "Dados invalidos.")

    arquivos = Arquivos()
    try:
        prep = preparar_versao(db, contract, gen, contrato_data, arquivos)
    except Exception as e:
        logger.error("Falha ao gerar a edicao de %s: %s", contract_id, e)
        raise HTTPException(500, MSG_ERRO_INTERNO)

    # Distrato que gerou um substabelecimento: mudar os dados aqui regera aquele documento.
    regerados: list[str] = []
    criados: list[str] = []
    if contract.tipo_contrato == TIPO_DISTRATO:
        try:
            regerados, criados = sincronizar_do_distrato(db, contract, body.form_data, user.email, arquivos)
        except Exception as e:
            db.rollback()
            arquivos.desfazer()
            logger.error("Falha ao atualizar o substabelecimento do distrato %s: %s", contract_id, e)
            raise HTTPException(500, MSG_ERRO_INTERNO)

    new_version = prep.numero
    client_name, client_email = cliente_do_form_data(body.form_data)
    gravar_versao(
        db, contract, prep,
        form_data_json=json.dumps(body.form_data, ensure_ascii=False),
        client_name=client_name, client_email=client_email, user_email=user.email,
        acao="edicao", detalhe=f"Nova versao {new_version} gerada por {user.name}",
    )
    _atualizar_documentos_do_cliente(db, contract, body.form_data, contrato_data, user)

    try:
        confirmar(db, arquivos)  # nada de .docx sem registro
    except Exception as e:
        logger.error("Falha ao gravar a edicao de %s: %s", contract_id, e)
        raise HTTPException(500, MSG_ERRO_INTERNO)

    return {
        "success": True,
        "message": f"Contrato atualizado (versao {new_version})",
        "contract_id": contract_id,
        "version": new_version,
        "download_url": f"/api/contract/{contract_id}/download",
        "documentos_regerados": regerados,
        "documentos_gerados_junto": criados,
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

    exigir_acesso_ao_contrato(contract, user)

    valid_statuses = {"rascunho", "enviado", "assinado", "cancelado"}
    if status not in valid_statuses:
        raise HTTPException(422, f"Status invalido. Validos: {valid_statuses}")

    old_status = contract.status
    if old_status == "assinado" and status != "assinado":
        raise HTTPException(409, "Contrato assinado não muda de status. Para alterar algo, crie um aditivo.")
    if old_status == "enviado" and status in ("rascunho", "cancelado"):
        raise HTTPException(409, "Para sair de \"enviado\" use \"Cancelar envio para assinatura\" (arquiva o link no DocuSeal).")
    if status == "assinado" and old_status not in ("rascunho", "enviado", "assinado"):
        raise HTTPException(409, f"Contrato {old_status} não pode ser marcado como assinado.")
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
    registrar_auditoria(db, contract_id, "mudanca_status", detalhe, user_email=user.email)

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

    exigir_acesso_ao_contrato(contract, user)
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
        carregado = carregar_versao(target_ver)
        form_data, contrato_data, gen = carregado.form_data, carregado.request, carregado.gerador
    except Exception:
        # str(ValidationError) traz input_value= (dados do cliente): so' no log.
        logger.exception("Dados da versao %s de %s invalidos", version, contract_id)
        raise HTTPException(422, f"Dados da versao {version} invalidos.")

    arquivos = Arquivos()
    try:
        prep = preparar_versao(db, contract, gen, contrato_data, arquivos)
    except Exception as e:
        logger.error("Falha ao gerar a reversao de %s: %s", contract_id, e)
        raise HTTPException(500, MSG_ERRO_INTERNO)

    new_version = prep.numero
    client_name, client_email = cliente_do_form_data(form_data)
    gravar_versao(
        db, contract, prep,
        form_data_json=target_ver.form_data_json,
        client_name=client_name, client_email=client_email, user_email=user.email,
        acao="rollback",
        detalhe=f"Revertido para versao {version} (nova versao {new_version}) por {user.email}",
    )
    _atualizar_documentos_do_cliente(db, contract, form_data, contrato_data, user)

    try:
        confirmar(db, arquivos)
    except Exception as e:
        logger.error("Falha ao gravar a reversao de %s: %s", contract_id, e)
        raise HTTPException(500, MSG_ERRO_INTERNO)

    return {
        "success": True,
        "message": f"Contrato revertido para versao {version} (nova versao {new_version})",
        "contract_id": contract_id,
        "version": new_version,
    }
