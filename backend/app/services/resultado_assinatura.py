"""Resultado da assinatura: o que muda no contrato quando o DocuSeal conclui, recusa ou o envio e' cancelado.

Tres caminhos chegam aqui — o webhook do DocuSeal, a sincronizacao da tela e o
cancelamento — e todos usam as mesmas regras, entao elas moram num lugar so'.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.database import AuditLogDB, ContractDB, ContractVersionDB, utcnow
from app.models.documentos_complementares import ROTULO_DOCUMENTO, TIPO_DISTRATO, TIPOS_COMPLEMENTARES
from app.services import email_financeiro, servicos_externos
from app.services.ciclo_contrato import registrar_auditoria

logger = logging.getLogger(__name__)

class EnvioNaoCancelavel(Exception):
    """O contrato nao esta aguardando assinaturas, ou nao tem envio registrado."""


class DocuSealNaoConfirmou(Exception):
    """O DocuSeal nao confirmou o cancelamento; nada foi alterado aqui."""


def conclusao_docuseal(status_data: dict[str, Any]) -> str | None:
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


def refletir_na_origem(contract: ContractDB, db: Session) -> None:
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
        registrar_auditoria(db, origem.contract_id, acao, f"{rotulo} assinado ({contract.contract_id})")
    if contract.tipo_contrato == TIPO_DISTRATO and origem.status != "encerrado":
        origem.status = "encerrado"
        origem.updated_at = utcnow()
        registrar_auditoria(
            db, origem.contract_id, "encerramento",
            f"Contrato encerrado por distrato assinado ({contract.contract_id})",
        )
    db.commit()


async def aplicar_conclusao(
    contract: ContractDB,
    version: ContractVersionDB,
    novo_status: str,
    acao: str,
    detalhe: str,
    db: Session,
) -> None:
    """Grava o status final e, se assinado, manda a ficha ao financeiro.

    Idempotente dos dois lados: o DocuSeal reentrega webhook, e a sincronizacao
    pode rodar a cada abertura da pagina do contrato. A ficha sai uma vez so',
    mesmo com os dois caminhos juntos (ver email_financeiro.enviar_ficha_assinada).
    """
    # Trava a linha do contrato e le o estado de agora: com varios avisos juntos, cada um carregou o
    # contrato antes dos outros gravarem, e o status "antigo" em memoria faria todos registrarem a
    # mesma mudanca. (SQLite ignora o bloqueio; Postgres serializa.)
    db.query(ContractDB).filter(ContractDB.contract_id == contract.contract_id).with_for_update().first()
    db.refresh(contract)
    if contract.status != novo_status:
        contract.status = novo_status
        contract.updated_at = utcnow()
        registrar_auditoria(db, contract.contract_id, acao, detalhe, version.version_number)
        db.commit()
        logger.info("Contract %s updated to status '%s' (%s)", contract.contract_id, novo_status, acao)

    if novo_status != "assinado":
        return

    if contract.tipo_contrato in TIPOS_COMPLEMENTARES:
        # Documento complementar nao gera ficha de participacao; so' reflete no contrato de origem.
        refletir_na_origem(contract, db)
        return

    await email_financeiro.enviar_ficha_assinada(db, contract, version)


async def cancelar_envio(db: Session, contract: ContractDB, user_email: str) -> None:
    """Arquiva as submissoes no DocuSeal (os links enviados deixam de valer) e volta o contrato a rascunho.

    So para contrato 'enviado'. Se o DocuSeal recusar ou falhar, nada muda aqui.
    """
    if contract.status != "enviado":
        raise EnvioNaoCancelavel(
            "Só dá para cancelar o envio de um contrato que está aguardando assinaturas."
        )

    versoes = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract.contract_id,
                ContractVersionDB.docuseal_submission_id.isnot(None))
        .order_by(ContractVersionDB.version_number.desc())
        .all()
    )
    if not versoes:
        raise EnvioNaoCancelavel("Este contrato não tem envio para assinatura registrado.")

    service = servicos_externos.get_docuseal_service()
    for i, v in enumerate(versoes):
        sid = v.docuseal_submission_id
        try:
            ok = await service.archive_submission(sid)
        except Exception as e:
            logger.warning("Falha ao arquivar a submissao %s: %s", sid, e)
            ok = False
        if not ok and i == 0:  # a do envio atual precisa ser cancelada; as antigas ja' foram arquivadas no reenvio
            raise DocuSealNaoConfirmou(
                "O DocuSeal não confirmou o cancelamento do envio. Nada foi alterado; tente de novo em instantes."
            )

    ids_submissoes = {v.docuseal_submission_id for v in versoes}
    nao_encontradas = [s for s in getattr(service, "nao_encontradas", []) if s in ids_submissoes]
    nota_404 = (
        f" O DocuSeal respondeu 404 para a submissão {', '.join(nao_encontradas)} (já apagada lá)."
        if nao_encontradas else ""
    )
    ids = ", ".join(v.docuseal_submission_id for v in versoes)
    for v in versoes:
        v.docuseal_submission_id = None
    contract.status = "rascunho"
    contract.updated_by = user_email
    contract.updated_at = utcnow()
    registrar_auditoria(
        db, contract.contract_id, "cancelamento_envio",
        f"Envio para assinatura cancelado (submissão DocuSeal {ids}); contrato voltou a rascunho.{nota_404}",
        contract.current_version, user_email,
    )
    db.commit()
