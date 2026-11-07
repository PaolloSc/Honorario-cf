from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import AuditLogDB, ColaboradorDB, ContractDB, ContractVersionDB, get_db, utcnow
from app.models.documentos_complementares import ROTULO_DOCUMENTO, TIPO_DISTRATO, TIPOS_COMPLEMENTARES
from app.services.arquivo_contrato import ArquivoNaoEncontrado
from app.services.docuseal import link_assinatura
from app.services import assinatura, servicos_externos
from app.utils.participacao import linhas_participacao
from app.utils.erros import MSG_ERRO_DOCUSEAL, MSG_ERRO_INTERNO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docuseal", tags=["DocuSeal"])

DOCUSEAL_WEBHOOK_SECRET = settings.docuseal_webhook_secret


class DocuSealRequest(BaseModel):
    contract_id: str
    signatarios: list[dict[str, str]]

    # O front manda null em campos opcionais (ex.: phone sem WhatsApp); o pydantic
    # recusava com "Input should be a valid string" e o envio nao saia.
    @field_validator("signatarios", mode="before")
    @classmethod
    def _sem_nulos(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return v
        return [
            {k: str(x) for k, x in s.items() if x is not None} if isinstance(s, dict) else s
            for s in v
        ]


class DocuSealResponse(BaseModel):
    success: bool
    message: str
    submission_id: str | None = None
    # Contratantes com link e WhatsApp: a tela abre o WhatsApp logo apos o envio.
    whatsapp: list[dict[str, str]] = []


def socio_sugerido(form_data_json: str | None, db: Session) -> ColaboradorDB | None:
    """Socio pre-selecionado na tela para assinar pelo escritorio (o usuario pode trocar).

    O responsavel pela gestao, se for socio; senao o primeiro socio entre os que
    recebem participacao (regra do PR #74).
    """
    from app.models.contract import Participacao

    if not form_data_json:
        return None
    try:
        form_data = json.loads(form_data_json)
    except ValueError:
        return None

    socios = (
        db.query(ColaboradorDB)
        .filter(
            ColaboradorDB.papel == "socio",
            ColaboradorDB.ativo.is_(True),
            ColaboradorDB.email.isnot(None),
        )
        .all()
    )

    try:
        participacao = Participacao(**(form_data.get("participacao") or {}))
    except Exception:
        return None
    por_nome = {s.nome: s for s in socios}
    for nome in [participacao.responsavel_gestao] + [p.nome for p in participacao.participantes]:
        socio = por_nome.get((nome or "").strip())
        if socio:
            return socio
    return None


@router.post("/send-for-signature", response_model=DocuSealResponse)
async def send_for_signature(
    data: DocuSealRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocuSealResponse:
    """Send contract for digital signature via DocuSeal."""
    try:
        r = await assinatura.enviar(db, data.contract_id, data.signatarios, user.email)
    except assinatura.EnvioInvalido as e:
        raise HTTPException(400, str(e))
    except ArquivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Contract file not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DocuSeal error: %s", e)
        raise HTTPException(status_code=500, detail=MSG_ERRO_INTERNO)
    return DocuSealResponse(
        success=r.success,
        message=r.message,
        submission_id=r.submission_id,
        whatsapp=[_assinante_para_tela(s) for s in r.contratantes],
    )


async def _send_contract_to_financeiro(
    contract_id: str,
    filepath: str,
    contract: ContractDB | None,
    db: Session,
    user: CurrentUser,
) -> None:
    """Send a copy of the contract to the financeiro email."""
    try:
        email_service = servicos_externos.get_email_service()
        client_name = contract.client_name if contract else "Cliente"

        result = await email_service.send_email_with_attachment(
            to_email=settings.financeiro_email,
            to_name="Financeiro C&F",
            subject=f"Cópia Contrato de Honorários — {client_name}",
            attachment_path=filepath,
            attachment_name=f"contrato_honorarios_{contract_id}.docx",
        )

        if result.get("success"):
            logger.info("Contract copy sent to financeiro for contract %s", contract_id)
            if contract:
                db.add(AuditLogDB(
                    contract_id=contract_id,
                    action="envio_copia_financeiro",
                    detail=f"Cópia do contrato enviada para {settings.financeiro_email}",
                    version_number=contract.current_version,
                    user_email=user.email,
                    created_at=utcnow(),
                ))
                db.commit()
        else:
            logger.warning("Failed to send contract copy to financeiro: %s", result.get("error"))
    except Exception as e:
        logger.error("Error sending contract copy to financeiro: %s", e)


async def _send_participacao_to_financeiro(
    contract_id: str,
    contract: ContractDB | None,
    latest_ver: ContractVersionDB | None,
    db: Session,
    user_email: str,
    contract_filepath: str | None = None,
    momento_label: str = "Assinatura concluída por todas as partes",
    subject_prefix: str = "Ficha de Participação (Assinado)",
    audit_action: str = "envio_participacao_final",
) -> None:
    """Send participação sheet to financeiro based on stored form data.

    Disparada quando TODAS as partes assinaram (webhook submission.completed).
    `user_email` identifica quem originou o contrato (sem CurrentUser no webhook).
    """
    try:
        if not latest_ver or not latest_ver.form_data_json:
            return

        form_data = json.loads(latest_ver.form_data_json)
        participacao = form_data.get("participacao", {})

        if not participacao.get("tem_participacao"):
            return

        client_name = contract.client_name if contract else "Cliente"

        # Extract "Objeto do Contrato" from escopos - mirror ALL fields the lawyer filled
        ESCOPO_LABELS = {
            "consultoria_contencioso_geral": "Consultoria e contencioso nas areas de atuacao do C&F",
            "contencioso_representacao": "Contencioso para representacao e atuacao em autos",
            "contencioso_memoriais": "Contencioso para Memoriais e sustentacao oral",
            "contencioso_tutela_urgencia": "Contencioso para tutela de urgencia",
            "consultoria_lgpd": "Consultoria LGPD",
            "consultoria_compliance_trabalhista": "Compliance Trabalhista",
            "consultoria_planejamento_tributario": "Planejamento tributario",
            "consultoria_diagnostico_fiscal": "Diagnostico fiscal",
            "consultoria_planejamento_patrimonial": "Planejamento patrimonial",
            "consultoria_estruturacao_societaria": "Estruturacao societaria",
            "consultoria_contratual": "Analise contratual",
            "consultoria_elaboracao_documentos": "Elaboracao de documentos",
            "consultoria_opiniao_legal": "Opiniao legal / Parecer",
            "outro": "",
        }

        escopos = form_data.get("escopos", [])
        escopo_descriptions = []
        for escopo in escopos:
            parts = []
            tipo = escopo.get("tipo_escopo") or escopo.get("tipo", "")
            label = ESCOPO_LABELS.get(tipo, "")

            # Main label (skip for "outro" since descricao_custom will cover it)
            if label and tipo != "outro":
                parts.append(label)

            # Custom description
            desc = escopo.get("escopo_personalizado") or escopo.get("descricao_custom", "")
            if desc:
                parts.append(desc)

            # Process number
            numero_autos = escopo.get("numero_autos", "")
            if numero_autos:
                parts.append(f"Processo: {numero_autos}")

            # Demands
            demandas = escopo.get("demandas", "")
            if demandas:
                parts.append(f"Demandas: {demandas}")

            # People/assets
            pessoas = escopo.get("pessoas_patrimonios", "")
            if pessoas:
                parts.append(f"Pessoas/Patrimonios: {pessoas}")

            # Restructuring type
            reestruturacao = escopo.get("tipo_reestruturacao", "")
            if reestruturacao:
                parts.append(f"Reestruturacao: {reestruturacao}")

            # Documents
            documentos = escopo.get("documentos", "")
            if documentos:
                parts.append(f"Documentos: {documentos}")

            # Legal opinion topic
            consulta = escopo.get("consulta", "")
            if consulta:
                parts.append(f"Consulta: {consulta}")

            # Memorial activities
            subtipo = escopo.get("subtipo_memoriais", {})
            if subtipo:
                atividades = []
                if subtipo.get("elaboracao_memoriais"):
                    atividades.append("Elaboracao de Memoriais")
                if subtipo.get("despacho_memoriais"):
                    atividades.append("Despacho de Memoriais")
                if subtipo.get("sustentacao_oral_relator"):
                    atividades.append("Sustentacao oral c/ Relator")
                if subtipo.get("sustentacao_oral_todos_julgadores"):
                    atividades.append("Sustentacao oral c/ todos os julgadores")
                if atividades:
                    parts.append(f"Atividades: {', '.join(atividades)}")

            if parts:
                escopo_descriptions.append(" | ".join(parts))

        objeto_contrato = "\n".join(escopo_descriptions) if escopo_descriptions else "Nao especificado"

        rows = []
        # Objeto do contrato is the FIRST field (as requested by financeiro)
        # Replace newlines with <br> for HTML rendering
        rows.append(("Objeto do Contrato", objeto_contrato.replace("\n", "<br>")))
        rows.extend(linhas_participacao(participacao))

        if not rows:
            return

        table_rows = "".join(
            f'<tr><td style="padding:8px;border:1px solid #D7D1CA;font-weight:600;">{k}</td>'
            f'<td style="padding:8px;border:1px solid #D7D1CA;">{v}</td></tr>'
            for k, v in rows
        )

        html = (
            '<div style="font-family: Segoe UI, Tahoma, sans-serif; max-width: 600px;">'
            '<div style="background-color: #1A3C34; padding: 20px 28px; border-radius: 8px 8px 0 0;">'
            '<span style="color: #FFFFFF; font-size: 16px; font-weight: 500;">Ficha de Participação — Uso Interno</span>'
            '</div>'
            '<div style="padding: 24px; border: 1px solid #D7D1CA; border-top: none; border-radius: 0 0 8px 8px;">'
            f'<p><strong>Cliente:</strong> {client_name}</p>'
            f'<p><strong>Contrato:</strong> {contract_id}</p>'
            f'<p><strong>Registrado por:</strong> {user_email}</p>'
            f'<p><strong>Momento:</strong> {momento_label}</p>'
            '<table style="width:100%;border-collapse:collapse;margin-top:16px;">'
            f'{table_rows}'
            '</table>'
            '</div></div>'
        )

        email_service = servicos_externos.get_email_service()

        # Send with contract attachment if filepath is available
        if contract_filepath and Path(contract_filepath).exists():
            result = await email_service.send_html_email_with_attachment(
                to_email=settings.financeiro_email,
                to_name="Financeiro C&F",
                subject=f"{subject_prefix} — {client_name}",
                html_content=html,
                attachment_path=contract_filepath,
                attachment_name=f"contrato_honorarios_{contract_id}.docx",
            )
        else:
            result = await email_service.send_html_email(
                to_email=settings.financeiro_email,
                to_name="Financeiro C&F",
                subject=f"{subject_prefix} — {client_name}",
                html_content=html,
            )

        if result.get("success"):
            logger.info("Participacao sheet sent to financeiro for contract %s", contract_id)
            if contract:
                db.add(AuditLogDB(
                    contract_id=contract_id,
                    action=audit_action,
                    detail=f"Ficha de participação enviada para {settings.financeiro_email}",
                    version_number=contract.current_version,
                    user_email=user_email,
                    created_at=utcnow(),
                ))
                db.commit()
        else:
            logger.warning("Failed to send participacao to financeiro: %s", result.get("error"))
    except Exception as e:
        logger.error("Error sending participacao to financeiro: %s", e)


# ── Webhook (no auth — called externally by DocuSeal) ───────────


def _conclusao_docuseal(status_data: dict[str, Any]) -> str | None:
    """Traduz o estado de uma submissao do DocuSeal para o nosso status.

    Devolve "assinado", "recusado" ou None (ainda em andamento). O DocuSeal
    mudou o formato entre versoes — ora resume em `status`, ora so' marca
    `completed_at` em cada signatario — entao olhamos os tres sinais.
    """
    submitters = status_data.get("submitters") or []
    resumo = str(status_data.get("status") or "").lower()

    if resumo == "declined" or any(s.get("declined_at") for s in submitters):
        return "recusado"
    if resumo == "completed" or status_data.get("completed_at"):
        return "assinado"
    if submitters and all(s.get("completed_at") for s in submitters):
        return "assinado"
    return None


def _assinante_para_tela(s: dict[str, Any]) -> dict[str, str]:
    """Um signatario do DocuSeal com o link de assinatura e o WhatsApp dele."""
    return {
        "role": s.get("role", ""),
        "name": s.get("name", ""),
        "email": s.get("email", ""),
        # A criacao traz embed_src; a consulta so' o slug.
        "link": s.get("embed_src") or link_assinatura(settings.docuseal_base_url, s.get("slug") or ""),
        "whatsapp": s.get("phone") or "",
    }


def _pendentes_docuseal(status_data: dict[str, Any]) -> list[dict[str, str]]:
    """Signatarios que ainda nao assinaram nem recusaram, pra mostrar na tela."""
    submitters = status_data.get("submitters") or []
    return [
        _assinante_para_tela(s)
        for s in submitters
        if not s.get("completed_at") and not s.get("declined_at")
    ]


def _refletir_na_origem(contract: ContractDB, db: Session) -> None:
    """Aditivo assinado so' deixa auditoria no contrato de origem; distrato assinado o encerra.

    Idempotente: o DocuSeal reentrega webhook e a sincronizacao roda a cada abertura da pagina.
    """
    if not contract.contrato_origem_id:
        return
    origem = db.query(ContractDB).filter(ContractDB.contract_id == contract.contrato_origem_id).first()
    if origem is None:
        return
    rotulo = ROTULO_DOCUMENTO[contract.tipo_contrato]
    acao = f"{contract.tipo_contrato}_assinado"
    ja_registrado = (
        db.query(AuditLogDB.id)
        .filter(AuditLogDB.contract_id == origem.contract_id, AuditLogDB.action == acao,
                AuditLogDB.detail.like(f"%{contract.contract_id}%"))
        .first()
    )
    if not ja_registrado:
        db.add(AuditLogDB(
            contract_id=origem.contract_id, action=acao, created_at=utcnow(),
            detail=f"{rotulo} assinado ({contract.contract_id})",
        ))
    if contract.tipo_contrato == TIPO_DISTRATO and origem.status != "encerrado":
        origem.status = "encerrado"
        origem.updated_at = utcnow()
        db.add(AuditLogDB(
            contract_id=origem.contract_id, action="encerramento", created_at=utcnow(),
            detail=f"Contrato encerrado por distrato assinado ({contract.contract_id})",
        ))
    db.commit()


async def _aplicar_conclusao(
    contract: ContractDB,
    version: ContractVersionDB,
    novo_status: str,
    acao: str,
    detalhe: str,
    db: Session,
) -> None:
    """Grava o status final e, se assinado, manda a ficha ao financeiro.

    Idempotente dos dois lados: o DocuSeal reentrega webhook, e a sincronizacao
    pode rodar a cada abertura da pagina do contrato.
    """
    if contract.status != novo_status:
        contract.status = novo_status
        contract.updated_at = utcnow()
        db.add(AuditLogDB(
            contract_id=contract.contract_id,
            action=acao,
            detail=detalhe,
            version_number=version.version_number,
            created_at=utcnow(),
        ))
        db.commit()
        logger.info("Contract %s updated to status '%s' (%s)", contract.contract_id, novo_status, acao)

    if novo_status != "assinado":
        return

    if contract.tipo_contrato in TIPOS_COMPLEMENTARES:
        # Documento complementar nao gera ficha de participacao; so' reflete no contrato de origem.
        _refletir_na_origem(contract, db)
        return

    ja_enviada = (
        db.query(AuditLogDB)
        .filter(
            AuditLogDB.contract_id == contract.contract_id,
            AuditLogDB.action == "envio_participacao_final",
        )
        .first()
    )
    if not ja_enviada:
        await _send_participacao_to_financeiro(
            contract.contract_id,
            contract,
            version,
            db,
            user_email=contract.created_by or "sistema",
        )


class DocuSealWebhookPayload(BaseModel):
    event_type: str
    data: dict[str, Any] = {}


@router.post("/webhook")
async def docuseal_webhook(
    payload: DocuSealWebhookPayload,
    x_docuseal_secret: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Receive webhook events from DocuSeal (submission.completed / submission.declined)."""
    # Validate webhook secret
    if not DOCUSEAL_WEBHOOK_SECRET or x_docuseal_secret != DOCUSEAL_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    event_type = payload.event_type
    data = payload.data
    submission_id = str(data.get("id", data.get("submission_id", "")))

    logger.info("DocuSeal webhook received: event=%s submission_id=%s", event_type, submission_id)

    if event_type not in ("submission.completed", "submission.declined"):
        return {"status": "ignored", "event_type": event_type}

    new_status = "assinado" if event_type == "submission.completed" else "recusado"

    # Find the contract version that matches this submission
    version = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.docuseal_submission_id == submission_id)
        .first()
    )
    if not version:
        logger.warning("No contract version found for submission_id=%s", submission_id)
        return {"status": "not_found", "submission_id": submission_id}

    contract = db.query(ContractDB).filter(ContractDB.contract_id == version.contract_id).first()
    if contract:
        await _aplicar_conclusao(
            contract,
            version,
            new_status,
            f"webhook_{new_status}",
            f"DocuSeal webhook: {event_type} (submission {submission_id})",
            db,
        )

    return {"status": "ok", "new_status": new_status}


# ── Status check (authenticated) ────────────────────────────────


class DocuSealStatusResponse(BaseModel):
    contract_id: str
    submission_id: str
    status: dict[str, Any]


@router.get("/{contract_id}/status", response_model=DocuSealStatusResponse)
async def get_docuseal_status(
    contract_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check the signing status of a contract via DocuSeal API."""
    latest_version = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract_id)
        .order_by(ContractVersionDB.version_number.desc())
        .first()
    )

    if not latest_version or not latest_version.docuseal_submission_id:
        raise HTTPException(status_code=404, detail="No DocuSeal submission found for this contract")

    submission_id = latest_version.docuseal_submission_id
    service = servicos_externos.get_docuseal_service()
    status_data = await service.get_submission_status(submission_id)

    return DocuSealStatusResponse(
        contract_id=contract_id,
        submission_id=submission_id,
        status=status_data,
    )


class PendenteSigner(BaseModel):
    role: str
    name: str
    email: str
    link: str = ""
    whatsapp: str = ""


class SincronizacaoResponse(BaseModel):
    contract_id: str
    status: str
    alterado: bool
    detalhe: str
    pendentes: list[PendenteSigner] = []


@router.post("/{contract_id}/cancelar-envio")
async def cancelar_envio_assinatura(
    contract_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Arquiva a submissao no DocuSeal (o link enviado deixa de valer) e volta o contrato a rascunho.

    So para contrato 'enviado'. Se o DocuSeal recusar ou falhar, nada muda aqui.
    """
    from app.routers.contracts import _check_access

    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    _check_access(contract, user)
    if contract.status != "enviado":
        raise HTTPException(status_code=409, detail="Só dá para cancelar o envio de um contrato que está aguardando assinaturas.")

    versoes = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract_id, ContractVersionDB.docuseal_submission_id.isnot(None))
        .order_by(ContractVersionDB.version_number.desc())
        .all()
    )
    if not versoes:
        raise HTTPException(status_code=409, detail="Este contrato não tem envio para assinatura registrado.")

    service = servicos_externos.get_docuseal_service()
    arquivadas: list[str] = []
    for i, v in enumerate(versoes):
        sid = v.docuseal_submission_id
        try:
            ok = await service.archive_submission(sid)
        except Exception as e:
            logger.warning("Falha ao arquivar a submissao %s: %s", sid, e)
            ok = False
        if ok:
            arquivadas.append(sid)
        elif i == 0:  # a do envio atual precisa ser cancelada; as antigas ja' foram arquivadas no reenvio
            raise HTTPException(
                status_code=502,
                detail="O DocuSeal não confirmou o cancelamento do envio. Nada foi alterado; tente de novo em instantes.",
            )

    ids = ", ".join(v.docuseal_submission_id for v in versoes)
    nao_encontradas = [s for s in getattr(service, "nao_encontradas", []) if s in {v.docuseal_submission_id for v in versoes}]
    nota_404 = f" O DocuSeal respondeu 404 para a submissão {', '.join(nao_encontradas)} (já apagada lá)." if nao_encontradas else ""
    for v in versoes:
        v.docuseal_submission_id = None
    contract.status = "rascunho"
    contract.updated_by = user.email
    contract.updated_at = utcnow()
    db.add(AuditLogDB(
        contract_id=contract_id, action="cancelamento_envio",
        detail=f"Envio para assinatura cancelado (submissão DocuSeal {ids}); contrato voltou a rascunho.{nota_404}",
        version_number=contract.current_version, user_email=user.email, created_at=utcnow(),
    ))
    db.commit()
    return {"success": True, "status": contract.status}


@router.post("/{contract_id}/sincronizar", response_model=SincronizacaoResponse)
async def sincronizar_status_assinatura(
    contract_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Le a submissao no DocuSeal e conclui o contrato se todos ja' assinaram.

    O webhook e' o caminho normal, mas ele depende de configuracao externa
    (DOCUSEAL_WEBHOOK_SECRET e o webhook cadastrado no DocuSeal) e de a chamada
    chegar. Quando falta qualquer uma das duas pontas, o contrato ficava preso em
    "enviado" para sempre, mesmo com todas as assinaturas colhidas — e so' dava
    para destravar mudando o status na mao. Aqui o proprio sistema pergunta ao
    DocuSeal em vez de esperar ser avisado.
    """
    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    version = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract_id)
        .order_by(ContractVersionDB.version_number.desc())
        .first()
    )
    if not version or not version.docuseal_submission_id:
        raise HTTPException(status_code=404, detail="Contrato não foi enviado para assinatura")

    status_anterior = contract.status
    service = servicos_externos.get_docuseal_service()
    try:
        status_data = await service.get_submission_status(version.docuseal_submission_id)
    except Exception as e:
        logger.warning("Falha ao consultar submissao %s: %s", version.docuseal_submission_id, e)
        raise HTTPException(status_code=502, detail=MSG_ERRO_DOCUSEAL)

    conclusao = _conclusao_docuseal(status_data)
    if not conclusao:
        pendentes = _pendentes_docuseal(status_data)
        nomes = ", ".join(f"{p['name']} ({p['role']})" for p in pendentes if p["name"])
        detalhe = (
            f"Ainda faltam assinar: {nomes}."
            if nomes
            else "Ainda há assinaturas pendentes no DocuSeal."
        )
        return SincronizacaoResponse(
            contract_id=contract_id,
            status=contract.status,
            alterado=False,
            detalhe=detalhe,
            pendentes=pendentes,
        )

    await _aplicar_conclusao(
        contract,
        version,
        conclusao,
        f"sync_{conclusao}",
        f"Status confirmado junto ao DocuSeal (submission {version.docuseal_submission_id})",
        db,
    )

    alterado = contract.status != status_anterior
    return SincronizacaoResponse(
        contract_id=contract_id,
        status=contract.status,
        alterado=alterado,
        detalhe=(
            "Todas as partes assinaram — contrato concluído."
            if conclusao == "assinado"
            else "Assinatura recusada no DocuSeal."
        ) if alterado else "O status já estava atualizado.",
    )
