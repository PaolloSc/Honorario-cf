from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.acesso import Capacidade, pode, pode_acessar_contrato
from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import (
    ContractDB,
    ParticipacaoDB,
    get_db,
    utcnow,
)
from app.models.contract import ContratoRequest, ContratoResponse
from app.models.contrato_consumidor import (
    TIPO_CONSUMIDOR_AEREO,
    ContratoConsumidorRequest,
    email_contato,
    nome_exibicao,
)
from app.services import contract_reviewer
from app.services.arquivo_contrato import ArquivoNaoEncontrado, VersaoNaoEncontrada, nome_do_anexo, resolver_arquivo
from app.services.ciclo_contrato import Arquivos, confirmar, criar, registrar_auditoria
from app.services.contrato_carregado import (
    TIPO_HONORARIOS,
    cliente_do_form_data,
)
from app.services.contrato_carregado import get_generator as get_consumidor_gen
from app.services.contract_generator import ContractGenerator
from app.services.previa_contrato import (
    PreviaHonorariosRequest,
    docx_para_html,
    html_do_documento,
    previa_com_itens,
    previa_honorarios,
)
from app.utils.participacao import valor_participacao, valor_participante
from app.utils.erros import MSG_ERRO_INTERNO


def get_consumidor_generator():
    return get_consumidor_gen(TIPO_CONSUMIDOR_AEREO)


def _emails_consumidor() -> set[str]:
    return {e.strip().lower() for e in settings.consumidor_emails.split(",") if e.strip()}


def pode_usar_consumidor(user: CurrentUser) -> bool:
    """Contrato de consumo e' restrito a equipe indicada pelo escritorio."""
    return pode(user, Capacidade.ADMINISTRAR) or user.email.lower() in _emails_consumidor()


def exigir_acesso_consumidor(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not pode_usar_consumidor(user):
        raise HTTPException(403, "Sem permissão para o contrato de Ação de Consumo")
    return user


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


_EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
_PCT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def _parse_percentual(text: str | None) -> float:
    """Extrai primeiro numero seguido de % do texto livre. '10% de 5000' -> 10.0."""
    if not text:
        return 0.0
    m = _PCT_RE.search(text)
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return 0.0


def _parse_email(text: str | None) -> str | None:
    if not text:
        return None
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _map_natureza_wizard(natureza_text: str | None) -> tuple[bool, bool]:
    """Retorna (eh_captacao, eh_performance) com base no texto livre da wizard."""
    if not natureza_text:
        return False, False
    s = natureza_text.lower()
    eh_cap = "capta" in s
    eh_perf = "perform" in s
    if not eh_cap and not eh_perf:
        # Default: assume captacao se texto livre nao bate
        eh_cap = True
    return eh_cap, eh_perf

def campos_rascunho_participacao(data: ContratoRequest, user_email: str, user_name: str) -> dict:
    """Campos da ficha de participacao (rascunho) derivados do wizard; usado ao criar e ao editar."""
    tipo = _infer_tipo_honorario(data)
    participacao_data = data.participacao

    participantes_wizard = (participacao_data.participantes if participacao_data else None) or []

    # Parse valores da wizard
    pct = _parse_percentual(
        participacao_data.percentual_ou_valor if participacao_data else None
    )
    # Natureza vem agora por advogado; usa a do primeiro participante como base.
    primeira_natureza = participantes_wizard[0].natureza if participantes_wizard else None
    eh_cap, eh_perf = _map_natureza_wizard(primeira_natureza)
    pct_captacao = pct if eh_cap else 0.0
    pct_performance = pct if eh_perf else 0.0

    # Email: prioriza campo estruturado novo, fallback parse do legado, fallback user.
    email_novo = (participacao_data.contato_financeiro_email or "").strip() if participacao_data else ""
    email_wizard = email_novo or _parse_email(
        participacao_data.contato_financeiro_cliente if participacao_data else None
    )
    beneficiario_email = email_wizard or user_email
    # Nome: junta os nomes de todos os participantes. Fallback user_name.
    beneficiario_nome = (
        ", ".join(p.nome for p in participantes_wizard) if participantes_wizard else user_name
    )

    # Backend natureza = contratual/societario (campo legal, nao wizard)
    natureza_val = "contratual"

    # Motivos: usa texto da wizard quando aplicável
    motivo_cap = (
        participacao_data.responsavel_captacao
        if participacao_data and pct_captacao > 0 and participacao_data.responsavel_captacao
        else None
    )
    motivo_perf = (
        participacao_data.responsavel_gestao
        if participacao_data and pct_performance > 0 and participacao_data.responsavel_gestao
        else None
    )

    obs_extra = ""
    if participacao_data:
        # Mesma formatacao da ficha (R$ 5.000,00, nao R$ 5000.00).
        valor_geral = valor_participacao(participacao_data.model_dump())
        valor_str = valor_geral[1] if valor_geral else "-"
        participantes_str = "; ".join(
            f"{p.nome} ({p.natureza or '-'}, {valor_participante(p.model_dump()) or 'geral'})"
            for p in participantes_wizard
        ) or "-"
        obs_extra = (
            f"Rascunho automatico do wizard. "
            f"Captacao responsavel: {participacao_data.responsavel_captacao or '-'} · "
            f"Gestao: {participacao_data.responsavel_gestao or '-'} · "
            f"Valor wizard: {valor_str} · "
            f"Participantes: {participantes_str}"
        )
    else:
        obs_extra = "Rascunho automatico do wizard."

    return {
        "beneficiario_email": beneficiario_email,
        "beneficiario_nome": beneficiario_nome or "",
        "tipo_honorario": tipo,
        "percentual_captacao": pct_captacao,
        "percentual_performance": pct_performance,
        "motivo_captacao": motivo_cap,
        "motivo_performance": motivo_perf,
        "natureza": natureza_val,
        "cliente_cpf_cnpj": _extract_cpf_cnpj(data),
        "observacoes": obs_extra,
    }


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contract", tags=["Contract"])

def get_generator() -> ContractGenerator:
    return get_consumidor_gen(TIPO_HONORARIOS)


@router.post("/generate", response_model=ContratoResponse)
def generate_contract(
    data: ContratoRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContratoResponse:
    arquivos = Arquivos()
    try:
        form_dict = data.model_dump(mode="json")
        client_name, client_email = cliente_do_form_data(form_dict)
        contract_id, _ = criar(
            db, arquivos,
            gerador=get_generator(), request=data, tipo=TIPO_HONORARIOS, form_dict=form_dict,
            client_name=client_name, client_email=client_email, user_email=user.email,
            detalhe=f"Contrato gerado para {client_name}",
        )

        # ── Plano A: cria Participação rascunho automática para o financeiro ──
        # Percentuais zerados + aprovada=False. Setor financeiro complementa e aprova.
        try:
            rascunho = ParticipacaoDB(
                **campos_rascunho_participacao(data, user.email, user.name),
                contract_id=contract_id,
                data_inicio=utcnow().date(),
                vinculo_ativo=True,
                aprovada=False,
                created_by=user.email,
                created_at=utcnow(),
            )
            db.add(rascunho)
            registrar_auditoria(
                db, contract_id, "participacao_rascunho",
                f"Rascunho automático criado para revisão do financeiro (tipo={rascunho.tipo_honorario})",
                user_email=user.email,
            )
        except Exception as part_err:
            # Não bloqueia geração de contrato se falhar criação do rascunho
            logger.warning("Falha ao criar participação rascunho automática: %s", part_err)

        confirmar(db, arquivos)

        logger.info("Contract generated by %s: %s", user.email, contract_id)

        return ContratoResponse(
            success=True,
            message="Contrato gerado com sucesso",
            contract_id=contract_id,
            download_url=f"/api/contract/{contract_id}/download",
        )
    except Exception as e:
        db.rollback()
        arquivos.desfazer()
        logger.error("Failed to generate contract: %s", e)
        raise HTTPException(status_code=500, detail=MSG_ERRO_INTERNO)


@router.post("/preview-texto")
def preview_texto(data: ContratoRequest, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Previa + clausulas ajustaveis, sem IA e sem gravar (usada ao salvar um ajuste)."""
    return previa_com_itens(data, get_generator())


@router.post("/review")
def review_contract(
    data: ContratoRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Previa + varredura de portugues/padrao via DeepSeek antes da geracao definitiva.
    Nao grava nada: o docx fica so na memoria, para a previa em HTML.
    A revisao olha so' os campos de texto livre que quem preenche o wizard digitou
    (nao a clausula padrao do contrato, que nao ha' onde editar ali). A previa
    (preview_html) e' sempre retornada; achados so' quando DEEPSEEK_API_KEY esta
    configurada (enabled=False caso contrario, sem erro)."""
    try:
        previa = previa_com_itens(data, get_generator())

        if not contract_reviewer.is_configured():
            return {"enabled": False, "findings": [], **previa}

        aplicados = {i["id"] for i in previa["itens"] if i["ajustado"]}
        text = contract_reviewer.extract_open_fields(data.model_dump(mode="json"), aplicados)
        findings = contract_reviewer.review_text(text) if text.strip() else []
        findings = contract_reviewer.so_do_digitado(findings, data.model_dump(mode="json"), aplicados)
        return {"enabled": True, "findings": findings, **previa}
    except contract_reviewer.ContractReviewError as e:
        logger.warning("Revisao do contrato indisponivel: %s", e)
        return {"enabled": True, "findings": [], **previa, "error": "Revisão por IA indisponível no momento."}
    except Exception as e:
        logger.error("Falha na revisao do contrato: %s", e)
        raise HTTPException(status_code=500, detail=MSG_ERRO_INTERNO)


@router.post("/generate-consumidor", response_model=ContratoResponse)
def generate_contrato_consumidor(
    data: ContratoConsumidorRequest,
    user: CurrentUser = Depends(exigir_acesso_consumidor),
    db: Session = Depends(get_db),
) -> ContratoResponse:
    """Contrato de consumidor/aereo. Sem ficha de participacao: honorario e' fixo (25%)."""
    arquivos = Arquivos()
    try:
        primeiro = data.contratantes[0]
        client_name = nome_exibicao(primeiro)
        form_dict = data.model_dump(mode="json")
        contract_id, _ = criar(
            db, arquivos,
            gerador=get_consumidor_generator(), request=data, tipo=TIPO_CONSUMIDOR_AEREO, form_dict=form_dict,
            client_name=client_name, client_email=email_contato(primeiro), user_email=user.email,
            detalhe=f"Contrato de consumidor gerado para {client_name}",
        )
        confirmar(db, arquivos)

        logger.info("Consumer contract generated by %s: %s", user.email, contract_id)

        return ContratoResponse(
            success=True,
            message="Contrato gerado com sucesso",
            contract_id=contract_id,
            download_url=f"/api/contract/{contract_id}/download",
        )
    except Exception as e:
        db.rollback()
        arquivos.desfazer()
        logger.error("Failed to generate consumer contract: %s", e)
        raise HTTPException(status_code=500, detail=MSG_ERRO_INTERNO)


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
    if not pode_acessar_contrato(user, contract):
        raise HTTPException(403, "Sem permissao")

    try:
        filepath = resolver_arquivo(contract_id, db, version, provisorio=True)
    except VersaoNaoEncontrada:
        raise HTTPException(404, f"Versao {version} nao encontrada")
    except ArquivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    return FileResponse(
        path=str(filepath),
        filename=nome_do_anexo(contract.client_name, contract_id, contract.tipo_contrato or TIPO_HONORARIOS),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/consumidor/acesso")
def acesso_consumidor(user: CurrentUser = Depends(get_current_user)) -> dict:
    """O frontend usa isto para mostrar (ou nao) o menu de Ação de Consumo."""
    return {"permitido": pode_usar_consumidor(user)}


@router.post("/preview-consumidor", response_class=HTMLResponse)
def preview_contrato_consumidor(
    data: ContratoConsumidorRequest,
    user: CurrentUser = Depends(exigir_acesso_consumidor),
) -> HTMLResponse:
    """Previa do contrato de consumidor antes de gravar: nada vai para o banco.

    Gera o DOCX num arquivo temporario so' para converter em HTML. Nao usa o gerador
    em cache — trocar o output_dir de um singleton afetaria geracoes simultaneas.
    """
    from app.services.consumidor_generator import ConsumidorGenerator

    try:
        return HTMLResponse(content=html_do_documento(ConsumidorGenerator()._build_document(data)))
    except Exception as e:
        logger.error("Failed to preview consumer contract: %s", e)
        raise HTTPException(status_code=500, detail=MSG_ERRO_INTERNO)


@router.post("/preview-honorarios")
def preview_honorarios(
    body: PreviaHonorariosRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Previa so' da secao de honorarios, para o pop-up do wizard: o texto digitado
    vem destacado e, com revisar=True, a correcao da IA aparece no lugar. Nada e' gravado."""
    return previa_honorarios(body, get_generator())


@router.get("/{contract_id}/preview", response_class=HTMLResponse)
def preview_contract(
    contract_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Inline HTML preview of the latest contract version."""
    try:
        uuid.UUID(contract_id)
    except ValueError:
        raise HTTPException(400, "ID de contrato inválido")

    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(404, "Contrato nao encontrado")
    if not pode_acessar_contrato(user, contract):
        raise HTTPException(403, "Sem permissao")

    try:
        filepath = resolver_arquivo(contract_id, db)
    except ArquivoNaoEncontrado:
        raise HTTPException(404, "Contract file not found")
    return HTMLResponse(docx_para_html(Path(filepath)))
