from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import ContractDB, get_db
from app.services.previa_contrato import _SIG_TAG
from app.services.arquivo_contrato import ArquivoNaoEncontrado, nome_do_anexo, resolver_arquivo
from app.services import email_financeiro, servicos_externos
from app.services.ciclo_contrato import registrar_auditoria
from app.services.contrato_carregado import tipo_da_versao, ultima_versao
from app.utils.participacao import linhas_participacao
from app.utils.erros import MSG_ERRO_EMAIL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["Email"])


class EmailRequest(BaseModel):
    contract_id: str
    destinatario_email: str
    destinatario_nome: str
    assunto: str = "Contrato de Honorários - C&F Advogados"


class EmailResponse(BaseModel):
    success: bool
    message: str


LOLista = Annotated[
    list[Annotated[str, StringConstraints(max_length=256)]],
    Field(max_length=50),
]


class ParticipacaoEmailRequest(BaseModel):
    contract_id: str
    cliente_nome: str
    objeto_contrato: str = ""
    # Valor estruturado
    valor_tipo: str = ""           # "percentual" | "valor" | "outro"
    valor_percentual: str = ""
    valor_monetario: float | None = None
    valor_outro: str = ""
    # Advogados (cada um com natureza e percentual próprios)
    participantes: list[dict] = []
    responsavel_captacao: str = ""
    responsavel_gestao: str = ""
    # Contato financeiro (3 campos)
    contato_financeiro_nome: str = ""
    contato_financeiro_email: str = ""
    contato_financeiro_telefone: str = ""
    # Base da participacao
    base_tipo: str = ""
    base_escopo_index: int | None = None
    base_honorario: str = ""
    base_label: str = ""
    # Cadastro no Legal One (limites alinhados a coluna legalone_opcoes.valor)
    categoria_cliente: str = Field("", max_length=256)
    etiquetas: LOLista = []
    listas_transmissao: LOLista = []
    # Legados
    percentual_ou_valor: str = ""
    contato_financeiro_cliente: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, data):
        if isinstance(data, dict):
            for field in ("objeto_contrato", "valor_tipo", "valor_percentual",
                          "valor_outro", "responsavel_captacao",
                          "responsavel_gestao", "contato_financeiro_nome",
                          "contato_financeiro_email", "contato_financeiro_telefone",
                          "percentual_ou_valor", "contato_financeiro_cliente",
                          "categoria_cliente", "base_tipo", "base_honorario",
                          "base_label"):
                if data.get(field) is None:
                    data[field] = ""
            for field in ("etiquetas", "listas_transmissao"):
                v = data.get(field)
                if isinstance(v, str):
                    data[field] = [v] if v.strip() else []
                elif v is None:
                    data[field] = []
            if data.get("participantes") is None:
                data["participantes"] = []
        return data


def _docx_review_copy(src: Path) -> Path:
    """Cópia de conferência do DOCX para o cliente: troca as merge-tags do DocuSeal
    ({{...;type=signature;...}}) por linhas de assinatura. Não altera o arquivo
    original, que segue com as tags para o fluxo do DocuSeal. Em qualquer falha
    (arquivo não é DOCX válido, erro ao salvar) devolve o próprio `src` — o chamador
    só apaga o resultado quando ele difere de `src`."""
    from docx import Document

    try:
        doc = Document(str(src))
    except Exception as exc:  # arquivo nao e um DOCX valido (ex.: placeholder)
        logger.warning("Nao foi possivel abrir DOCX %s para conferencia: %s", src, exc)
        return src

    def _fix(paras) -> None:
        for p in paras:
            if _SIG_TAG.search(p.text):
                novo = _SIG_TAG.sub("_" * 40, p.text)
                for r in p.runs:
                    r.text = ""
                if p.runs:
                    p.runs[0].text = novo
                else:
                    p.add_run(novo)

    _fix(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                _fix(cell.paragraphs)

    # Caminho único por requisição: evita corrida entre chamadas concorrentes
    # para o mesmo contrato (que compartilhariam review_{stem}.docx).
    fd, tmp_name = tempfile.mkstemp(prefix="review_", suffix=src.suffix or ".docx")
    os.close(fd)
    try:
        doc.save(tmp_name)
    except (OSError, ValueError) as exc:
        logger.warning("Falha ao salvar copia de conferencia de %s: %s", src, exc)
        Path(tmp_name).unlink(missing_ok=True)
        return src
    return Path(tmp_name)


def _tipo_do_contrato(contract_id: str, db: Session) -> str:
    """Define o rotulo do anexo: honorarios ou prestacao de servicos."""
    ver = ultima_versao(db, contract_id)
    return tipo_da_versao(ver.form_data_json if ver else None)


@router.post("/send", response_model=EmailResponse)
async def send_contract_email(
    data: EmailRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailResponse:
    """Send contract via email using Azure Communication Services."""
    try:
        try:
            filepath = resolver_arquivo(data.contract_id, db)
        except ArquivoNaoEncontrado:
            raise HTTPException(status_code=404, detail="Contract file not found")
        contract = db.query(ContractDB).filter(ContractDB.contract_id == data.contract_id).first()

        review_path = _docx_review_copy(filepath)
        attachment_name = nome_do_anexo(
            contract.client_name if contract else None,
            data.contract_id,
            _tipo_do_contrato(data.contract_id, db),
        )

        service = servicos_externos.get_email_service()
        try:
            result = await service.send_email_with_attachment(
                to_email=data.destinatario_email,
                to_name=data.destinatario_nome,
                subject=data.assunto,
                attachment_path=str(review_path),
                attachment_name=attachment_name,
                cc_email=user.email,  # advogado logado recebe junto com o cliente
            )
        finally:
            if review_path != filepath:
                review_path.unlink(missing_ok=True)

        if result["success"]:
            if contract:
                registrar_auditoria(db, data.contract_id, "envio_email", f"E-mail enviado para {data.destinatario_email}", contract.current_version, user.email)
                db.commit()
            return EmailResponse(success=True, message="E-mail enviado com sucesso")
        else:
            logger.error("Falha no envio de e-mail: %s", result.get("error"))
            return EmailResponse(success=False, message=MSG_ERRO_EMAIL)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        raise HTTPException(status_code=500, detail=MSG_ERRO_EMAIL)


@router.post("/send-participacao", response_model=EmailResponse)
async def send_participacao_email(
    data: ParticipacaoEmailRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailResponse:
    """Send participation internal sheet to financeiro."""
    try:
        # Use objeto_contrato from request; if empty, build from stored form data
        objeto_contrato = data.objeto_contrato.strip()
        if not objeto_contrato:
            objeto_contrato = email_financeiro.objeto_do_contrato_salvo(data.contract_id, db)

        rows = []
        # Objeto do Contrato first (as requested by financeiro)
        # A quebra de linha vira <br> no laco que monta a tabela, depois do escape.
        if objeto_contrato:
            rows.append(("Objeto do Contrato", objeto_contrato))
        rows.extend(linhas_participacao(data.model_dump()))

        # ponytail: participacao inferida dos proprios campos em vez de uma flag nova.
        # O wizard so manda estes campos quando o toggle esta ligado, mas a inferencia
        # cobre todos eles: uma ficha com apenas o responsavel preenchido ainda e
        # participacao, e rotula-la "Cadastro Legal One" seria mentira.
        # Contato financeiro e responsavel_gestao NAO entram aqui: sao sempre
        # enviados, com ou sem participacao.
        tem_participacao = any((
            data.base_label,
            data.valor_tipo,
            data.participantes,
            data.responsavel_captacao,
            data.percentual_ou_valor,
        ))
        titulo = "Ficha de Participação" if tem_participacao else "Cadastro Legal One"

        html = email_financeiro.montar_ficha_html(
            titulo=titulo,
            cliente=data.cliente_nome,
            contract_id=data.contract_id,
            registrado_por=user.email,
            linhas=rows,
        )

        # Arquivo do contrato (refeito do banco se o disco o perdeu); sem ele, vai sem anexo
        try:
            contract_filepath = str(resolver_arquivo(data.contract_id, db))
        except ArquivoNaoEncontrado:
            contract_filepath = None

        result = await email_financeiro.enviar_ficha(
            assunto=f"{titulo} — {data.cliente_nome}",
            html=html,
            anexo_path=contract_filepath,
            anexo_nome=nome_do_anexo(data.cliente_nome, data.contract_id),
        )

        if result["success"]:
            contract = db.query(ContractDB).filter(ContractDB.contract_id == data.contract_id).first()
            if contract:
                registrar_auditoria(db, data.contract_id, "envio_ficha_participacao", f"Ficha de participação enviada para {settings.financeiro_email}", contract.current_version, user.email)
                db.commit()
            return EmailResponse(success=True, message="Ficha enviada para o financeiro")

        logger.error("Falha no envio da ficha: %s", result.get("error"))
        return EmailResponse(success=False, message=MSG_ERRO_EMAIL)

    except Exception as e:
        logger.error("Failed to send participacao email: %s", e)
        raise HTTPException(status_code=500, detail=MSG_ERRO_EMAIL)
