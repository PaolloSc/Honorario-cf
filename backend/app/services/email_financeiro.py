"""E-mails ao financeiro: a ficha de participacao (uso interno).

Um so' lugar monta o texto e a tabela da ficha, tanto para o envio manual (tela do
contrato) quanto para o automatico (quando todas as partes assinam).
"""
from __future__ import annotations

import json
import logging
from html import escape
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.config import settings
from app.database import AuditLogDB, ContractDB, ContractVersionDB
from app.models.contract import ESCOPO_LABELS, TipoEscopo
from app.services import servicos_externos
from app.services.ciclo_contrato import registrar_auditoria
from app.utils.participacao import linhas_participacao

logger = logging.getLogger(__name__)

ACAO_FICHA_FINAL = "envio_participacao_final"

_CAMPOS_DO_ESCOPO = (
    ("numero_autos", "Processo"),
    ("demandas", "Demandas"),
    ("pessoas_patrimonios", "Pessoas/Patrimônios"),
    ("tipo_reestruturacao", "Reestruturação"),
    ("documentos", "Documentos"),
    ("consulta", "Consulta"),
)
_ATIVIDADES_MEMORIAIS = (
    ("elaboracao_memoriais", "Elaboração de memoriais"),
    ("despacho_memoriais", "Despacho de memoriais"),
    ("sustentacao_oral_relator", "Sustentação oral c/ Relator"),
    ("sustentacao_oral_todos_julgadores", "Sustentação oral c/ todos os julgadores"),
)


def objeto_do_contrato(form_data: dict[str, Any]) -> str:
    """Texto do 'Objeto do Contrato' a partir dos escopos preenchidos (uma linha por escopo)."""
    linhas: list[str] = []
    for escopo in form_data.get("escopos") or []:
        partes: list[str] = []
        tipo_raw = escopo.get("tipo_escopo") or escopo.get("tipo", "")
        try:
            rotulo = ESCOPO_LABELS.get(TipoEscopo(tipo_raw), tipo_raw)
        except ValueError:
            rotulo = tipo_raw
        if rotulo and tipo_raw != "outro":
            partes.append(rotulo)
        desc = escopo.get("descricao_custom") or escopo.get("escopo_personalizado")
        if desc:
            partes.append(desc)
        for chave, prefixo in _CAMPOS_DO_ESCOPO:
            if escopo.get(chave):
                partes.append(f"{prefixo}: {escopo[chave]}")

        memoriais = escopo.get("subtipo_memoriais") or {}
        atividades = [texto for campo, texto in _ATIVIDADES_MEMORIAIS if memoriais.get(campo)]
        if atividades:
            partes.append(f"Atividades: {', '.join(atividades)}")

        if partes:
            linhas.append(" | ".join(partes))
    return "\n".join(linhas)


def objeto_do_contrato_salvo(contract_id: str, db: Session) -> str:
    """O mesmo texto, a partir da ultima versao gravada (quando a tela nao o mandou)."""
    ver = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract_id)
        .order_by(ContractVersionDB.version_number.desc())
        .first()
    )
    if not ver or not ver.form_data_json:
        return ""
    try:
        return objeto_do_contrato(json.loads(ver.form_data_json))
    except (ValueError, TypeError):
        return ""


# Campos que so' valem com participacao: o wizard guarda o que foi digitado antes de
# desligar a chave, e isso nao pode chegar ao financeiro como se o contrato tivesse participacao.
_CAMPOS_DE_PARTICIPACAO = (
    "valor_tipo", "valor_percentual", "valor_monetario", "valor_outro", "percentual_ou_valor",
    "participantes", "para_quem", "natureza", "responsavel_captacao",
    "base_tipo", "base_escopo_index", "base_honorario", "base_label",
)
LINHA_SEM_PARTICIPACAO = ("Participação", "Sem participação")


def linhas_da_ficha(objeto: str, participacao: Mapping[str, Any], tem_participacao: bool) -> list[tuple[str, str]]:
    """Linhas da ficha: objeto, depois a participacao (ou 'Sem participacao') e o cadastro do financeiro.

    A ficha sai sempre; sem participacao ela diz isso, em vez de omitir o assunto.
    """
    linhas: list[tuple[str, str]] = [("Objeto do Contrato", objeto)] if objeto else []
    if tem_participacao:
        return linhas + linhas_participacao(participacao)
    resto = {k: v for k, v in participacao.items() if k not in _CAMPOS_DE_PARTICIPACAO}
    return linhas + [LINHA_SEM_PARTICIPACAO] + linhas_participacao(resto)


def montar_ficha_html(
    *,
    titulo: str,
    cliente: str,
    contract_id: str,
    registrado_por: str,
    linhas: list[tuple[str, str]],
    momento: str | None = None,
) -> str:
    """HTML da ficha. Tudo que veio de formulario e' escapado; quebra de linha vira <br> depois disso."""
    tabela = "".join(
        f'<tr><td style="padding:8px;border:1px solid #D7D1CA;font-weight:600;">{escape(k)}</td>'
        f'<td style="padding:8px;border:1px solid #D7D1CA;">{escape(str(v)).replace(chr(10), "<br>")}</td></tr>'
        for k, v in linhas
    )
    linha_momento = f"<p><strong>Momento:</strong> {escape(momento)}</p>" if momento else ""
    return (
        '<div style="font-family: Segoe UI, Tahoma, sans-serif; max-width: 600px;">'
        '<div style="background-color: #1A3C34; padding: 20px 28px; border-radius: 8px 8px 0 0;">'
        f'<span style="color: #FFFFFF; font-size: 16px; font-weight: 500;">{escape(titulo)} — Uso Interno</span>'
        '</div>'
        '<div style="padding: 24px; border: 1px solid #D7D1CA; border-top: none; border-radius: 0 0 8px 8px;">'
        f'<p><strong>Cliente:</strong> {escape(cliente)}</p>'
        f'<p><strong>Contrato:</strong> {escape(contract_id)}</p>'
        f'<p><strong>Registrado por:</strong> {escape(registrado_por)}</p>'
        f'{linha_momento}'
        '<table style="width:100%;border-collapse:collapse;margin-top:16px;">'
        f'{tabela}'
        '</table>'
        '</div></div>'
    )


async def enviar_ficha(
    *,
    assunto: str,
    html: str,
    anexo_path: str | None = None,
    anexo_nome: str = "",
) -> dict[str, Any]:
    """Manda o HTML ao financeiro, com o contrato em anexo quando houver."""
    servico = servicos_externos.get_email_service()
    if anexo_path:
        return await servico.send_html_email_with_attachment(
            to_email=settings.financeiro_email,
            to_name="Financeiro C&F",
            subject=assunto,
            html_content=html,
            attachment_path=anexo_path,
            attachment_name=anexo_nome,
        )
    return await servico.send_html_email(
        to_email=settings.financeiro_email,
        to_name="Financeiro C&F",
        subject=assunto,
        html_content=html,
    )


def _reservar_envio(db: Session, contract: ContractDB) -> bool:
    """Marca a ficha final como 'em envio' ANTES de mandar. False se outro caminho ja' a reservou.

    O webhook do DocuSeal e a sincronizacao da tela chegam juntos. Conferir so' depois
    do envio deixava os dois passarem (o e-mail demora e cede a vez ao outro). Reservar
    antes fecha a janela; o bloqueio da linha do contrato (Postgres) cobre processos diferentes.
    """
    db.query(ContractDB).filter(ContractDB.contract_id == contract.contract_id).with_for_update().first()
    ja = (
        db.query(AuditLogDB.id)
        .filter(AuditLogDB.contract_id == contract.contract_id, AuditLogDB.action == ACAO_FICHA_FINAL)
        .first()
    )
    if ja:
        db.rollback()
        return False
    registrar_auditoria(
        db, contract.contract_id, ACAO_FICHA_FINAL,
        f"Ficha de participação enviada para {settings.financeiro_email}",
        contract.current_version, contract.created_by or "sistema",
    )
    db.commit()
    return True


def _liberar_reserva(db: Session, contract_id: str) -> None:
    """O envio falhou: tira a marca para a proxima sincronizacao tentar de novo."""
    db.rollback()
    db.query(AuditLogDB).filter(
        AuditLogDB.contract_id == contract_id, AuditLogDB.action == ACAO_FICHA_FINAL
    ).delete(synchronize_session=False)
    db.commit()


async def enviar_ficha_assinada(db: Session, contract: ContractDB, version: ContractVersionDB | None) -> bool:
    """Ficha de participacao ao financeiro quando todas as partes assinaram. Uma vez so'.

    Devolve True se mandou. Sai sempre; sem participacao, diz "Sem participacao".
    """
    if not version:
        return False
    try:
        form_data = json.loads(version.form_data_json) if version.form_data_json else {}
    except (ValueError, TypeError):
        return False
    participacao = form_data.get("participacao") or {}
    tem_participacao = bool(participacao.get("tem_participacao"))

    contract_id = contract.contract_id
    if not _reservar_envio(db, contract):
        return False
    try:
        objeto = objeto_do_contrato(form_data) or "Não especificado"
        cliente = contract.client_name or "Cliente"
        html = montar_ficha_html(
            titulo="Ficha de Participação",
            cliente=cliente,
            contract_id=contract_id,
            registrado_por=contract.created_by or "sistema",
            linhas=linhas_da_ficha(objeto, participacao, tem_participacao),
            momento="Assinatura concluída por todas as partes",
        )
        resultado = await enviar_ficha(assunto=f"Ficha de Participação (Assinado) — {cliente}", html=html)
        if resultado.get("success"):
            logger.info("Participacao sheet sent to financeiro for contract %s", contract_id)
            return True
        logger.warning("Failed to send participacao to financeiro: %s", resultado.get("error"))
    except Exception as e:
        logger.error("Error sending participacao to financeiro: %s", e)
    _liberar_reserva(db, contract_id)
    return False
