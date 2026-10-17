"""Aditivo, distrato e substabelecimento de um contrato (issue #126).

Cada documento e' um contrato proprio (ContractDB com tipo_contrato e
contrato_origem_id), entao previa, download, edicao, e-mail e assinatura reaproveitam
os endpoints dos contratos. Aqui ficam so' a geracao e o pre-preenchimento.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import (
    AuditLogDB,
    ContractDB,
    ContractVersionDB,
    get_db,
    serialize_cliente_docs,
    utcnow,
)
from app.models.documentos_complementares import (
    REQUESTS,
    ROTULO_DOCUMENTO,
    TIPO_ADITIVO,
    TIPO_DISTRATO,
    TIPOS_COMPLEMENTARES,
    AditivoAnterior,
    SubstabelecimentoRequest,
    email_contato,
    nome_exibicao,
)
from app.routers.contract import _docx_to_html
from app.routers.contracts import _check_access
from app.services.contract_dispatch import get_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documentos", tags=["Documentos complementares"])


def _form_data_atual(contract: ContractDB, db: Session) -> dict:
    ver = (
        db.query(ContractVersionDB)
        .filter(
            ContractVersionDB.contract_id == contract.contract_id,
            ContractVersionDB.version_number == contract.current_version,
        )
        .first()
    )
    return json.loads(ver.form_data_json) if ver else {}


def _origem(contrato_id: str, user: CurrentUser, db: Session) -> ContractDB:
    origem = db.query(ContractDB).filter(ContractDB.contract_id == contrato_id).first()
    if not origem:
        raise HTTPException(404, "Contrato de origem não encontrado")
    _check_access(origem, user)
    if origem.tipo_contrato in TIPOS_COMPLEMENTARES:
        raise HTTPException(422, "O contrato de origem não pode ser outro documento complementar")
    return origem


def _derivados(origem_id: str, db: Session, tipo: str | None = None) -> list[ContractDB]:
    """Documentos derivados ainda validos (cancelados nao contam), do mais antigo ao mais novo."""
    q = db.query(ContractDB).filter(
        ContractDB.contrato_origem_id == origem_id, ContractDB.status != "cancelado"
    )
    if tipo:
        q = q.filter(ContractDB.tipo_contrato == tipo)
    return q.order_by(ContractDB.created_at, ContractDB.id).all()


def _aditivos_anteriores(origem_id: str, db: Session, so_assinados: bool = False) -> list[AditivoAnterior]:
    """Aditivos validos com o numero que ocupam (rascunho conta na numeracao). O distrato so' cita
    como celebrados os assinados, mantendo o numero de cada um."""
    anteriores = []
    for i, ad in enumerate(_derivados(origem_id, db, TIPO_ADITIVO), 1):
        if so_assinados and ad.status != "assinado":
            continue
        form = _form_data_atual(ad, db)
        anteriores.append(
            AditivoAnterior(
                numero=i,
                data_documento=form.get("data_documento") or ad.created_at.date().isoformat(),
                objeto=form.get("objeto", ""),
            )
        )
    return anteriores


def _data_contrato_origem(form: dict) -> str | None:
    """Data em que o contrato foi firmado, se o form_data do pai a tiver (senao o advogado preenche)."""
    return form.get("data_contrato_origem") or form.get("data_contrato") or None


@router.get("/prefill/{contrato_origem_id}")
def prefill(
    contrato_origem_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Dados do contrato de origem para abrir o formulario ja preenchido."""
    origem = _origem(contrato_origem_id, user, db)
    form = _form_data_atual(origem, db)
    return {
        "contratantes": form.get("contratantes") or [],
        "aditivos_existentes": len(_derivados(origem.contract_id, db, TIPO_ADITIVO)),
        "data_contrato_origem": _data_contrato_origem(form),
        "status_origem": origem.status,
        "aviso": None if origem.status == "assinado" else "O contrato de origem ainda não foi assinado.",
    }


def _montar(tipo: str, corpo: dict, user: CurrentUser, db: Session):
    """Valida o corpo e completa os campos que o servidor deriva do contrato de origem."""
    if tipo not in REQUESTS:
        raise HTTPException(404, f"Tipo de documento desconhecido: {tipo}")
    try:
        data = REQUESTS[tipo](**corpo)
    except ValidationError as e:
        raise RequestValidationError(e.errors())

    origem = _origem(data.contrato_origem_id, user, db) if data.contrato_origem_id else None
    aviso = None
    if origem is not None:
        aviso = None if origem.status == "assinado" else "O contrato de origem ainda não foi assinado."
        if not isinstance(data, SubstabelecimentoRequest):
            # Servidor manda nos campos derivados do contrato de origem.
            form_origem = _form_data_atual(origem, db)
            data.contratantes = form_origem.get("contratantes") or []
            # So aditivo assinado e' citado como celebrado; a numeracao conta tambem os rascunhos.
            data.aditivos_anteriores = _aditivos_anteriores(origem.contract_id, db, so_assinados=True)
            if tipo == TIPO_ADITIVO:
                data.numero = len(_derivados(origem.contract_id, db, TIPO_ADITIVO)) + 1
            if tipo == TIPO_DISTRATO and _derivados(origem.contract_id, db, TIPO_DISTRATO):
                raise HTTPException(409, "Já existe um distrato para este contrato")
    return data, origem, aviso


@router.post("/{tipo}/preview", response_class=HTMLResponse)
def previa_documento(
    tipo: str,
    corpo: dict = Body(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Previa do documento antes de gravar: nada vai para o banco."""
    data, _, _ = _montar(tipo, corpo, user, db)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        get_generator(tipo)._build_document(data).save(str(tmp_path))
        return HTMLResponse(_docx_to_html(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/{tipo}")
def gerar_documento(
    tipo: str,
    corpo: dict = Body(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    data, origem, aviso = _montar(tipo, corpo, user, db)

    try:
        contract_id, filepath = get_generator(tipo).generate(data)
        form_dict = data.model_dump(mode="json")
        nome = nome_exibicao(data)
        origem_id = origem.contract_id if origem else None

        db.add(ContractDB(
            contract_id=contract_id,
            status="rascunho",
            client_name=nome,
            client_email=email_contato(data),
            tipo_contrato=tipo,
            contrato_origem_id=origem_id,
            current_version=1,
            created_by=user.email,
            updated_by=user.email,
            created_at=utcnow(),
            updated_at=utcnow(),
            cliente_docs=serialize_cliente_docs(
                {"contratantes": [data.outorgante.model_dump()]}
                if isinstance(data, SubstabelecimentoRequest)
                else form_dict
            ),
        ))
        db.flush()
        db.add(ContractVersionDB(
            contract_id=contract_id,
            version_number=1,
            form_data_json=json.dumps(form_dict, ensure_ascii=False),
            file_path=filepath,
            created_by=user.email,
            created_at=utcnow(),
        ))
        rotulo = ROTULO_DOCUMENTO[tipo]
        db.add(AuditLogDB(
            contract_id=contract_id, action="criacao", version_number=1, user_email=user.email,
            detail=f"{rotulo} gerado para {nome}", created_at=utcnow(),
        ))
        if origem_id:
            db.add(AuditLogDB(
                contract_id=origem_id, action="documento_complementar", user_email=user.email,
                detail=f"{rotulo} criado ({contract_id})", created_at=utcnow(),
            ))
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Falha ao gerar %s: %s", tipo, e)
        raise HTTPException(500, str(e))

    logger.info("%s gerado por %s: %s", tipo, user.email, contract_id)
    return {
        "success": True,
        "message": f"{ROTULO_DOCUMENTO[tipo]} gerado com sucesso",
        "contract_id": contract_id,
        "download_url": f"/api/contract/{contract_id}/download",
        "aviso": aviso,
    }
