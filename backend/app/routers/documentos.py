"""Aditivo, distrato e substabelecimento de um contrato (issue #126).

Cada documento e' um contrato proprio (ContractDB com tipo_contrato e
contrato_origem_id), entao previa, download, edicao, e-mail e assinatura reaproveitam
os endpoints dos contratos. Aqui ficam so' a geracao e o pre-preenchimento.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import ContractDB, get_db
from app.models.documentos_complementares import (
    REQUESTS,
    ROTULO_DOCUMENTO,
    TIPO_ADITIVO,
    TIPO_DISTRATO,
    TIPO_SUBSTABELECIMENTO,
    TIPOS_COMPLEMENTARES,
    AditivoAnterior,
    DistratoRequest,
    SubstabelecimentoRequest,
)
from app.routers.contract import _docx_to_html
from app.routers.contracts import _check_access
from app.services.contract_dispatch import get_generator
from app.utils.erros import MSG_ERRO_INTERNO
from app.services.substabelecimento_vinculado import (
    MOTIVO_TRAVADO,
    acrescentar_processos,
    documento_do_outorgante,
    form_data_atual,
    gravar_novo,
    nova_versao,
    so_digitos,
    substabelecimento_do_distrato,
    substabelecimentos_do_outorgante,
    travado,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documentos", tags=["Documentos complementares"])


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
        form = form_data_atual(ad, db)
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
    form = form_data_atual(origem, db)
    return {
        "contratantes": form.get("contratantes") or [],
        "aditivos_existentes": len(_derivados(origem.contract_id, db, TIPO_ADITIVO)),
        "data_contrato_origem": _data_contrato_origem(form),
        "status_origem": origem.status,
        "aviso": None if origem.status == "assinado" else "O contrato de origem ainda não foi assinado.",
    }


def _erro_campo(campo: str, msg: str) -> RequestValidationError:
    return RequestValidationError([{"loc": ("body", campo), "msg": msg, "type": "value_error", "input": None}])


def _validar_distrato_origem(data: SubstabelecimentoRequest, user: CurrentUser, db: Session) -> None:
    """O distrato de onde o substabelecimento diz nascer existe e e' do mesmo cliente; senao 422."""
    distrato = db.query(ContractDB).filter(
        ContractDB.contract_id == data.distrato_origem_id, ContractDB.tipo_contrato == TIPO_DISTRATO,
        ContractDB.status != "cancelado",
    ).first()
    if not distrato:
        raise _erro_campo("distrato_origem_id", "Distrato de origem não encontrado")
    try:
        _check_access(distrato, user)
    except HTTPException:
        raise _erro_campo("distrato_origem_id", "Distrato de origem não encontrado")
    if data.contrato_origem_id and data.contrato_origem_id != distrato.contrato_origem_id:
        raise _erro_campo("distrato_origem_id", "O distrato é de outro contrato")
    docs = {
        so_digitos(c.get("cnpj") or c.get("cpf"))
        for c in (form_data_atual(distrato, db).get("contratantes") or [])
    }
    doc_outorgante = so_digitos(data.outorgante.cnpj or data.outorgante.cpf)
    if doc_outorgante and doc_outorgante not in docs:
        raise _erro_campo("distrato_origem_id", "O distrato é de outro cliente")


def _montar(tipo: str, corpo: dict, user: CurrentUser, db: Session):
    """Valida o corpo e completa os campos que o servidor deriva do contrato de origem."""
    if tipo not in REQUESTS:
        raise HTTPException(404, f"Tipo de documento desconhecido: {tipo}")
    try:
        data = REQUESTS[tipo](**corpo)
    except ValidationError as e:
        raise RequestValidationError(e.errors())

    if isinstance(data, DistratoRequest) and data.substabelecer_e_devolver and data.substabelecimento is None:
        raise RequestValidationError([{
            "loc": ("body", "substabelecimento"), "msg": "Informe quem recebe os poderes e os processos",
            "type": "missing", "input": None,
        }])

    origem = _origem(data.contrato_origem_id, user, db) if data.contrato_origem_id else None
    if isinstance(data, SubstabelecimentoRequest) and data.distrato_origem_id:
        _validar_distrato_origem(data, user, db)
    aviso = None
    if origem is not None:
        aviso = None if origem.status == "assinado" else "O contrato de origem ainda não foi assinado."
        if not isinstance(data, SubstabelecimentoRequest):
            # Servidor manda nos campos derivados do contrato de origem.
            form_origem = form_data_atual(origem, db)
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


def _processos_novos(existente: ContractDB, data: SubstabelecimentoRequest, db: Session) -> tuple[SubstabelecimentoRequest, int]:
    """O substabelecimento existente com os processos de `data` que ainda nao constam nele."""
    atual = SubstabelecimentoRequest(**form_data_atual(existente, db))
    todos = acrescentar_processos(atual.processos, data.processos)
    return atual.model_copy(update={"processos": todos}), len(todos) - len(atual.processos)


def _norm(texto: str) -> str:
    return " ".join((texto or "").casefold().split())


def _partes_diferem(atual: SubstabelecimentoRequest, data: SubstabelecimentoRequest) -> bool:
    """Substabelecentes, substabelecidos ou endereco informados diferem dos do documento existente.
    Acrescentar mantem as partes do documento: se a pessoa informou outras, o DOCX final diria que
    o processo foi substabelecido a quem ela nao escolheu."""
    def pessoas(lista) -> list[tuple]:
        return [(_norm(p.nome), _norm(p.oab)) for p in lista]

    def substabelecentes(lista) -> list[tuple]:
        return [(_norm(p.nome), _norm(p.oab), _norm(p.email)) for p in lista]

    if substabelecentes(atual.substabelecentes) != substabelecentes(data.substabelecentes):
        return True
    if pessoas(atual.substabelecidos) != pessoas(data.substabelecidos):
        return True
    novo_endereco = _norm(data.endereco_substabelecidos)
    return bool(novo_endereco) and novo_endereco != _norm(atual.endereco_substabelecidos)


@router.get("/substabelecimento-existente")
def substabelecimento_existente(
    documento: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """O cliente (CPF/CNPJ) ja tem substabelecimento? Orienta 'acrescentar o processo' ou 'criar novo'."""
    for c in substabelecimentos_do_outorgante(db, so_digitos(documento)):
        try:
            _check_access(c, user)
        except HTTPException:
            continue
        lock = travado(c, db)
        form = form_data_atual(c, db)
        return {
            "existe": True,
            "contract_id": c.contract_id,
            "client_name": c.client_name,
            "status": c.status,
            "pode_acrescentar": not lock,
            "motivo": MOTIVO_TRAVADO if lock else None,
            "processos": [p.get("numero", "") for p in form.get("processos", [])],
            # A tela pre-preenche as partes com estas (no modo acrescentar elas valem para o documento todo).
            "substabelecentes": form.get("substabelecentes", []),
            "substabelecidos": form.get("substabelecidos", []),
            "endereco_substabelecidos": form.get("endereco_substabelecidos", ""),
        }
    return {"existe": False}


@router.post("/{tipo}")
def gerar_documento(
    tipo: str,
    corpo: dict = Body(...),
    acrescentar_a: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    data, origem, aviso = _montar(tipo, corpo, user, db)

    # Mesmo outorgante: acrescenta o(s) processo(s) ao substabelecimento existente (nova versao).
    if acrescentar_a and isinstance(data, SubstabelecimentoRequest):
        alvo = db.query(ContractDB).filter(ContractDB.contract_id == acrescentar_a).first()
        if not alvo or alvo.tipo_contrato != TIPO_SUBSTABELECIMENTO or alvo.status == "cancelado":
            raise HTTPException(404, "Substabelecimento a acrescentar não encontrado")
        _check_access(alvo, user)
        doc_alvo = documento_do_outorgante(form_data_atual(alvo, db))
        if not doc_alvo or doc_alvo != so_digitos(data.outorgante.cnpj or data.outorgante.cpf):
            raise HTTPException(422, "O substabelecimento a acrescentar é de outro outorgante")
        if travado(alvo, db):
            aviso = f"Foi criado um novo substabelecimento porque {MOTIVO_TRAVADO}."
        else:
            atual = SubstabelecimentoRequest(**form_data_atual(alvo, db))
            if _partes_diferem(atual, data):
                raise HTTPException(422, (
                    "As partes ou o endereço informados diferem do substabelecimento existente. "
                    "Para acrescentar o processo, mantenha os mesmos substabelecentes, substabelecidos e endereço; "
                    "para outras partes, crie um novo substabelecimento."
                ))
            combinado, novos = _processos_novos(alvo, data, db)
            if novos == 0 and combinado.model_dump(mode="json") == atual.model_dump(mode="json"):
                return {
                    "success": True, "message": "Os processos já constavam no substabelecimento",
                    "contract_id": alvo.contract_id, "download_url": f"/api/contract/{alvo.contract_id}/download",
                    "aviso": None, "documentos_gerados_junto": [], "acrescentado": True, "processos_novos": 0,
                }
            try:
                nova_versao(db, alvo, combinado, user.email, f"{novos} processo(s) acrescentado(s)")
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error("Falha ao acrescentar processo: %s", e)
                raise HTTPException(500, MSG_ERRO_INTERNO)
            return {
                "success": True, "message": "Processo acrescentado ao substabelecimento existente",
                "contract_id": alvo.contract_id, "download_url": f"/api/contract/{alvo.contract_id}/download",
                "aviso": None, "documentos_gerados_junto": [], "acrescentado": True, "processos_novos": novos,
            }

    # Todos os DOCX nascem juntos com os registros: se algo falhar, nenhum arquivo fica solto.
    arquivos: list[str] = []
    try:
        contract_id, arquivo = gravar_novo(db, tipo, data, origem, user.email)
        arquivos.append(arquivo)
        extras = []
        if isinstance(data, DistratoRequest) and data.substabelecer_e_devolver and data.substabelecimento:
            sub = substabelecimento_do_distrato(data, contract_id)
            cid, arquivo = gravar_novo(db, TIPO_SUBSTABELECIMENTO, sub, origem, user.email)
            arquivos.append(arquivo)
            extras.append(cid)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        for f in arquivos:
            Path(f).unlink(missing_ok=True)
        logger.error("Falha ao gerar %s: %s", tipo, e)
        raise HTTPException(500, str(e))

    logger.info("%s gerado por %s: %s", tipo, user.email, contract_id)
    return {
        "success": True,
        "message": f"{ROTULO_DOCUMENTO[tipo]} gerado com sucesso",
        "contract_id": contract_id,
        "download_url": f"/api/contract/{contract_id}/download",
        "aviso": aviso,
        "documentos_gerados_junto": extras,
    }
