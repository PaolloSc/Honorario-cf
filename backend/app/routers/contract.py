from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.database import (
    AuditLogDB,
    ContractDB,
    ContractVersionDB,
    ParticipacaoDB,
    get_db,
    serialize_cliente_docs,
    utcnow,
)
from app.models.contract import Acessorios, ContratoRequest, ContratoResponse, EscopoItem
from app.models.contrato_consumidor import (
    TIPO_CONSUMIDOR_AEREO,
    ContratoConsumidorRequest,
    email_contato,
    nome_exibicao,
)
from app.models.documentos_complementares import ROTULO_DOCUMENTO
from app.services import contract_reviewer
from app.services.contract_dispatch import TIPO_HONORARIOS
from app.services.contract_dispatch import get_generator as get_consumidor_gen
from app.services.contract_dispatch import parse_form_data
from app.services.contract_generator import ContractGenerator
from app.utils.participacao import valor_participacao, valor_participante


def get_consumidor_generator():
    return get_consumidor_gen(TIPO_CONSUMIDOR_AEREO)


def _emails_consumidor() -> set[str]:
    return {e.strip().lower() for e in settings.consumidor_emails.split(",") if e.strip()}


def pode_usar_consumidor(user: CurrentUser) -> bool:
    """Contrato de consumo e' restrito a equipe indicada pelo escritorio."""
    return user.role == "admin" or user.email.lower() in _emails_consumidor()


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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contract", tags=["Contract"])

_generator: ContractGenerator | None = None


def get_generator() -> ContractGenerator:
    global _generator
    if _generator is None:
        _generator = ContractGenerator()
    return _generator


def _extract_client_info(data: ContratoRequest) -> tuple[str, str]:
    if not data.contratantes:
        return ("", "")
    first = data.contratantes[0]
    name = getattr(first, "nome", None) or getattr(first, "razao_social", "")
    email = getattr(first, "email", "")
    return (name, email)


@router.post("/generate", response_model=ContratoResponse)
def generate_contract(
    data: ContratoRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContratoResponse:
    try:
        gen = get_generator()
        contract_id, filepath = gen.generate(data)

        client_name, client_email = _extract_client_info(data)
        form_dict = data.model_dump(mode="json")

        contract = ContractDB(
            contract_id=contract_id,
            status="rascunho",
            client_name=client_name,
            client_email=client_email,
            tipo_contrato=TIPO_HONORARIOS,
            current_version=1,
            created_by=user.email,
            updated_by=user.email,
            created_at=utcnow(),
            updated_at=utcnow(),
            cliente_docs=serialize_cliente_docs(form_dict),
        )
        db.add(contract)

        form_data_json = json.dumps(form_dict, ensure_ascii=False)
        version = ContractVersionDB(
            contract_id=contract_id,
            version_number=1,
            form_data_json=form_data_json,
            file_path=filepath,
            created_by=user.email,
            created_at=utcnow(),
        )
        db.add(version)

        audit = AuditLogDB(
            contract_id=contract_id,
            action="criacao",
            detail=f"Contrato gerado para {client_name}",
            version_number=1,
            user_email=user.email,
            created_at=utcnow(),
        )
        db.add(audit)

        # ── Plano A: cria Participação rascunho automática para o financeiro ──
        # Percentuais zerados + aprovada=False. Setor financeiro complementa e aprova.
        try:
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
            beneficiario_email = email_wizard or user.email
            # Nome: junta os nomes de todos os participantes. Fallback user.name.
            beneficiario_nome = (
                ", ".join(p.nome for p in participantes_wizard) if participantes_wizard else user.name
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

            rascunho = ParticipacaoDB(
                contract_id=contract_id,
                beneficiario_email=beneficiario_email,
                beneficiario_nome=beneficiario_nome or "",
                tipo_honorario=tipo,
                percentual_captacao=pct_captacao,
                percentual_performance=pct_performance,
                motivo_captacao=motivo_cap,
                motivo_performance=motivo_perf,
                natureza=natureza_val,
                cliente_cpf_cnpj=_extract_cpf_cnpj(data),
                data_inicio=utcnow().date(),
                vinculo_ativo=True,
                aprovada=False,
                observacoes=obs_extra,
                created_by=user.email,
                created_at=utcnow(),
            )
            db.add(rascunho)
            db.add(
                AuditLogDB(
                    contract_id=contract_id,
                    action="participacao_rascunho",
                    detail=f"Rascunho automático criado para revisão do financeiro (tipo={tipo})",
                    user_email=user.email,
                    created_at=utcnow(),
                )
            )
        except Exception as part_err:
            # Não bloqueia geração de contrato se falhar criação do rascunho
            logger.warning("Falha ao criar participação rascunho automática: %s", part_err)

        db.commit()

        logger.info("Contract generated by %s: %s", user.email, contract_id)

        return ContratoResponse(
            success=True,
            message="Contrato gerado com sucesso",
            contract_id=contract_id,
            download_url=f"/api/contract/{contract_id}/download",
        )
    except Exception as e:
        db.rollback()
        logger.error("Failed to generate contract: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review")
def review_contract(
    data: ContratoRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Previa + varredura de portugues/padrao via DeepSeek antes da geracao definitiva.
    Nao grava nada — gera o docx num arquivo temporario so' para a previa em HTML.
    A revisao olha so' os campos de texto livre que quem preenche o wizard digitou
    (nao a clausula padrao do contrato, que nao ha' onde editar ali). A previa
    (preview_html) e' sempre retornada; achados so' quando DEEPSEEK_API_KEY esta
    configurada (enabled=False caso contrario, sem erro)."""
    import tempfile

    gen = get_generator()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        gen._build_document(data).save(str(tmp_path))
        preview_html = _docx_to_html(tmp_path)

        if not contract_reviewer.is_configured():
            return {"enabled": False, "findings": [], "preview_html": preview_html}

        text = contract_reviewer.extract_open_fields(data.model_dump(mode="json"))
        findings = contract_reviewer.review_text(text) if text.strip() else []
        findings = contract_reviewer.so_do_digitado(findings, data.model_dump(mode="json"))
        return {"enabled": True, "findings": findings, "preview_html": preview_html}
    except contract_reviewer.ContractReviewError as e:
        logger.warning("Revisao do contrato indisponivel: %s", e)
        return {"enabled": True, "findings": [], "preview_html": preview_html, "error": str(e)}
    except Exception as e:
        logger.error("Falha na revisao do contrato: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


@router.post("/generate-consumidor", response_model=ContratoResponse)
def generate_contrato_consumidor(
    data: ContratoConsumidorRequest,
    user: CurrentUser = Depends(exigir_acesso_consumidor),
    db: Session = Depends(get_db),
) -> ContratoResponse:
    """Contrato de consumidor/aereo. Sem ficha de participacao: honorario e' fixo (25%)."""
    try:
        gen = get_consumidor_generator()
        contract_id, filepath = gen.generate(data)

        primeiro = data.contratantes[0]
        client_name = nome_exibicao(primeiro)
        form_dict = data.model_dump(mode="json")

        contract = ContractDB(
            contract_id=contract_id,
            status="rascunho",
            client_name=client_name,
            client_email=email_contato(primeiro),
            tipo_contrato=TIPO_CONSUMIDOR_AEREO,
            current_version=1,
            created_by=user.email,
            updated_by=user.email,
            created_at=utcnow(),
            updated_at=utcnow(),
            cliente_docs=serialize_cliente_docs(form_dict),
        )
        db.add(contract)
        db.add(
            ContractVersionDB(
                contract_id=contract_id,
                version_number=1,
                form_data_json=json.dumps(form_dict, ensure_ascii=False),
                file_path=filepath,
                created_by=user.email,
                created_at=utcnow(),
            )
        )
        db.add(
            AuditLogDB(
                contract_id=contract_id,
                action="criacao",
                detail=f"Contrato de consumidor gerado para {client_name}",
                version_number=1,
                user_email=user.email,
                created_at=utcnow(),
            )
        )
        db.commit()

        logger.info("Consumer contract generated by %s: %s", user.email, contract_id)

        return ContratoResponse(
            success=True,
            message="Contrato gerado com sucesso",
            contract_id=contract_id,
            download_url=f"/api/contract/{contract_id}/download",
        )
    except Exception as e:
        db.rollback()
        logger.error("Failed to generate consumer contract: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


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
    if user.role != "admin" and contract.created_by != user.email:
        raise HTTPException(403, "Sem permissao")

    # Find the file path from DB (specific version or latest)
    query = db.query(ContractVersionDB).filter(ContractVersionDB.contract_id == contract_id)
    if version:
        ver = query.filter(ContractVersionDB.version_number == version).first()
    else:
        ver = query.order_by(ContractVersionDB.version_number.desc()).first()

    gen = get_generator()
    output_dir = Path(gen.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath: Path | None = None

    if ver and ver.file_path:
        stored = Path(ver.file_path)
        if stored.exists():
            filepath = stored
        else:
            candidate = output_dir / stored.name
            if candidate.exists():
                filepath = candidate

    if filepath is None:
        fallback = output_dir / f"contrato_{contract_id}.docx"
        if fallback.exists():
            filepath = fallback

    # Strategy 4: Regenerate from form_data_json (handles ephemeral filesystems)
    if filepath is None and ver and ver.form_data_json:
        logger.warning(
            "Contract file not on disk for %s. Regenerating from stored form data...",
            contract_id,
        )
        try:
            form_data = json.loads(ver.form_data_json)
            # Cada tipo de contrato tem seu gerador — em FS efemero (serverless)
            # este e' o caminho normal de download, nao um caso de borda.
            contrato_data, gen_tipo = parse_form_data(form_data)
            _, new_filepath = gen_tipo.generate(contrato_data, contract_id=contract_id)
            filepath = Path(new_filepath)
            # Update stored path
            ver.file_path = str(filepath)
            db.commit()
            logger.info("Regenerated contract file at: %s", filepath)
        except FileNotFoundError as template_err:
            # Template not found (ephemeral FS) - create a minimal placeholder DOCX
            logger.warning("Template not found, creating minimal DOCX: %s", template_err)
            try:
                from docx import Document as _Doc
                doc = _Doc()
                doc.add_paragraph("Contrato em processamento - documento sera regenerado.")
                minimal_path = output_dir / f"contrato_{contract_id}.docx"
                doc.save(str(minimal_path))
                ver.file_path = str(minimal_path)
                db.commit()
                filepath = minimal_path
                logger.info("Created minimal placeholder DOCX at: %s", minimal_path)
            except Exception as min_err:
                logger.error("Failed to create minimal DOCX: %s", min_err)
        except Exception as regen_err:
            logger.error("Failed to regenerate contract %s: %s", contract_id, regen_err)

    if filepath is None or not filepath.exists():
        logger.error(
            "Contract file not found for %s. Tried: stored=%s, output_dir=%s",
            contract_id,
            ver.file_path if ver else "N/A",
            output_dir,
        )
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    return FileResponse(
        path=str(filepath),
        filename=_contract_filename(contract.client_name, contract_id, contract.tipo_contrato or TIPO_HONORARIOS),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


import re as _re

# DocuSeal merge-tag (ex.: "{{Assinatura Fulano;type=signature;role=Contratante}}").
# No preview trocamos por uma linha de assinatura para nao vazar a sintaxe crua.
_SIG_TAG = _re.compile(r"\{\{[^}]*?type=signature[^}]*?\}\}")

_FILENAME_BAD = _re.compile(r'[\r\n\t/\\:*?"<>|]+')


def _safe_filename_part(name: str) -> str:
    """Sanitiza um trecho vindo do usuário para uso em nome de arquivo/anexo."""
    cleaned = " ".join(_FILENAME_BAD.sub(" ", name).split())
    return cleaned[:120].strip()


def _contract_filename(
    client_name: str | None, contract_id: str, tipo: str = TIPO_HONORARIOS
) -> str:
    """Nome do anexo: o cliente precisa reconhecer o contrato pelo arquivo."""
    consumidor = tipo == TIPO_CONSUMIDOR_AEREO
    rotulo = ROTULO_DOCUMENTO.get(
        tipo, "Contrato de Prestação de Serviços" if consumidor else "Contrato Honorários"
    )
    generico = f"contrato_{'servicos' if consumidor else 'honorarios'}_{contract_id}.docx"

    nome = _safe_filename_part(client_name) if client_name else ""
    return f"{rotulo} — {nome}.docx" if nome else generico


def _clean_preview_text(text: str) -> str:
    # A tag do DocuSeal e' invisivel no Word (texto branco) e o documento ja traz
    # a linha de assinatura; deixa-la virar underscores duplicava a linha na previa.
    return _SIG_TAG.sub("", text)


def _clause_level(paragraph_el) -> int | None:
    """Nível do parágrafo na lista de cláusulas, ou None se não for numerado."""
    from docx.oxml.ns import qn

    num_pr = paragraph_el.find(qn("w:pPr") + "/" + qn("w:numPr"))
    if num_pr is None:
        return None
    ilvl = num_pr.find(qn("w:ilvl"))
    return int(ilvl.get(qn("w:val"))) if ilvl is not None else 0


def _inline_html(paragraph) -> str:
    """Preserva negrito dos runs (nomes e CONTRATANTE/CONTRATADA na qualificacao)."""
    from html import escape

    if not paragraph.runs:
        return escape(_clean_preview_text(paragraph.text))
    bits: list[str] = []
    for run in paragraph.runs:
        piece = escape(_clean_preview_text(run.text or ""))
        if not piece:
            continue
        bits.append(f"<strong>{piece}</strong>" if run.bold else piece)
    return "".join(bits) or escape(_clean_preview_text(paragraph.text))


def _docx_to_html(filepath: Path) -> str:
    """Render the generated DOCX as simple HTML for inline preview (no external deps)."""
    from html import escape

    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(filepath))
    parts: list[str] = []
    contadores = [0, 0, 0]  # niveis da lista de clausulas (o Word numera no .docx)
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, doc)
            text = _inline_html(p)
            if not text.strip():
                continue
            ilvl = _clause_level(child)
            if ilvl is not None:
                contadores[ilvl] += 1
                for abaixo in range(ilvl + 1, len(contadores)):
                    contadores[abaixo] = 0
                text = ".".join(str(n) for n in contadores[: ilvl + 1]) + ". " + text
            style = p.style.name if p.style else ""
            if style == "Heading 1":
                parts.append(f"<h1>{text}</h1>")
            elif style.startswith("Heading"):
                parts.append(f"<h3>{text}</h3>")
            else:
                parts.append(f"<p>{text}</p>")
        elif child.tag == qn("w:tbl"):
            t = Table(child, doc)
            has_borders = t._tbl.tblPr.first_child_found_in("w:tblBorders") is not None
            # <th> so' na linha marcada como cabecalho (w:tblHeader). A tabela do
            # milheiro nao tem titulo: a 1a linha ja e' dado.
            def _e_cabecalho(row) -> bool:
                trPr = row._tr.trPr
                return trPr is not None and trPr.find(qn("w:tblHeader")) is not None

            def celula_html(cell) -> str:
                # Cada paragrafo da celula e' uma linha. `cell.text` junta tudo num
                # texto so e o HTML colapsa a quebra: o rotulo da assinatura acabava
                # na mesma linha dos underscores.
                linhas = [
                    escape(_clean_preview_text(p.text)).strip() for p in cell.paragraphs
                ]
                return "<br>".join(linha for linha in linhas if linha)

            rows_html = "".join(
                "<tr>" + "".join(
                    f"<{'th' if _e_cabecalho(row) else 'td'}>{celula_html(c)}"
                    f"</{'th' if _e_cabecalho(row) else 'td'}>"
                    for c in row.cells
                ) + "</tr>"
                for row in t.rows
            )
            css = "" if has_borders else ' class="noborder"'
            parts.append(f"<table{css}>{rows_html}</table>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>"
        "body{font-family:'Segoe UI',sans-serif;max-width:800px;margin:2rem auto;"
        "font-size:.9rem;line-height:1.5;color:#000;background:#fff;padding:0 1rem}"
        "h1{text-align:center;font-size:1.1rem}"
        "h3{font-size:1rem;margin-top:1.2rem}"
        "p{text-align:justify}"
        "table{border-collapse:collapse;width:100%;margin:.5rem 0}"
        "td,th{border:1px solid #000;padding:6px}"
        "th{text-align:center}"
        "table.noborder td{border:none}"
        "</style></head>"
        f"<body>{''.join(parts)}</body></html>"
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
    import tempfile

    from app.services.consumidor_generator import ConsumidorGenerator

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        ConsumidorGenerator()._build_document(data).save(str(tmp_path))
        return HTMLResponse(content=_docx_to_html(tmp_path))
    except Exception as e:
        logger.error("Failed to preview consumer contract: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


# Contratante ficticio: na etapa 3 o cliente costuma estar pela metade e a
# previa de honorarios nao depende dele.
_CONTRATANTE_PREVIA = {
    "tipo": "PF", "nome": "Prévia", "nacionalidade": "brasileiro(a)", "cpf": "00000000000",
    "profissao": "-", "estado_civil": "Solteiro(a)", "endereco": "-", "email": "previa@cf.adv.br",
}


class PreviaHonorariosRequest(BaseModel):
    escopos: list[EscopoItem]
    acessorios: Optional[Acessorios] = None
    # True pede tambem a revisao de portugues da IA (lenta; o pop-up faz 2 chamadas).
    revisar: bool = False


_MARCA_DIGITADO = "background:rgba(250,204,21,.35);border-radius:2px;padding:0 1px"
_MARCA_RISCADO = "background:rgba(239,68,68,.18);color:#b91c1c;text-decoration:line-through"
_MARCA_IA = "background:rgba(34,197,94,.22);text-decoration:none;border-radius:2px;padding:0 1px"


def _padrao_do_texto(digitado: str):
    """Regex que acha no html o texto digitado, mesmo escrito um pouco diferente no
    contrato: inicial maiuscula/minuscula, espacos repetidos, aspas, ponto final.
    Com fronteira de palavra nas pontas ("sim" nao casa em "Assim") e fora de tags.
    Unica busca, usada para achar e para marcar. None se nao ha o que procurar."""
    from html import escape

    miolo = (digitado or "").strip().rstrip(".;, ").strip()
    if not miolo:
        return None
    partes: list[str] = []
    primeira = True
    for pedaco in re.split(r"(\s+)", miolo):
        if not pedaco:
            continue
        if pedaco.isspace():
            partes.append(r"\s+")
            continue
        for c in pedaco:
            if c in "\"'":
                partes.append("(?:" + "|".join(re.escape(x) for x in (c, escape(c), escape(c, quote=False), "&#39;")) + ")")
            elif primeira and c.isalpha():
                partes.append("[" + re.escape(c.lower()) + re.escape(c.upper()) + "]")
            else:
                partes.append(re.escape(escape(c)))
            primeira = False
    return re.compile(r"(?<!\w)" + "".join(partes) + r"(?!\w)(?![^<]*>)"), miolo


def _achar_no_html(html: str, digitado: str, destaque: bool = True) -> str | None:
    """Trecho do html que corresponde ao texto digitado, como esta no contrato (sem
    escape), ou None. Com destaque=True, texto curto (<12) ou so' numero/percentual
    ("10%") so' vale se tiver uma unica ocorrencia: melhor sem destaque que no lugar
    errado. destaque=False so' diz se o campo foi escrito no contrato (vai a IA)."""
    from html import unescape

    padrao = _padrao_do_texto(digitado)
    if not padrao:
        return None
    regex, miolo = padrao
    achados = [m.group(0) for m in regex.finditer(html)]
    if not achados:
        return None
    if destaque and (len(miolo) < 12 or not re.search(r"[^\W\d_]", miolo)) and len(achados) != 1:
        return None
    return unescape(achados[0])


def _marcar_digitados(html: str, textos: list, achados: list[dict]) -> str:
    """Amarelo = o que a pessoa digitou. Onde a IA propoe outro texto, o digitado sai
    riscado e a sugestao logo depois, em verde (o que o contrato recebe se aplicar).
    O mesmo texto digitado em mais de um honorario e' destacado em cada ocorrencia."""
    from html import escape

    # Cada trecho vira um intervalo; o mais longo vence quando dois se sobrepoem
    # (nada de <mark> dentro de <mark>), e o texto curto nunca cai dentro de tag.
    # Um item e' o texto ou (texto, trechos do html onde o gerador o escreveu): fora
    # desses trechos nunca marca. Cada item usa uma ocorrencia (texto igual em dois
    # honorarios = dois itens = duas marcas).
    itens = [(t, None) if isinstance(t, str) else t for t in textos]
    escolhidos: list[tuple[int, int, str]] = []
    for texto, spans in sorted(itens, key=lambda it: -len(it[0])):
        alvo = escape(texto)
        dentro = alvo
        for a in achados:
            bruto = (a.get("trecho") or "").strip()
            # a IA ve o texto como digitado; o contrato pode ter descido a inicial
            trecho = next((escape(t) for t in (bruto, bruto[:1].swapcase() + bruto[1:]) if t and escape(t) in dentro), "")
            if trecho:
                # ponytail: casa por substring; trecho dentro de sugestao ja inserida
                # nao e' tratado (o revisor ja descarta trechos aninhados).
                dentro = dentro.replace(
                    trecho,
                    f'<del style="{_MARCA_RISCADO}">{trecho}</del>'
                    f'<ins style="{_MARCA_IA}">{escape(a.get("sugestao") or "")}</ins>',
                    1,
                )
        marcado = f'<mark style="{_MARCA_DIGITADO}">{dentro}</mark>'
        regex = _padrao_do_texto(texto)[0]
        for m in regex.finditer(html):
            if spans is not None and not any(i0 <= m.start() and m.end() <= f for i0, f in spans):
                continue
            if any(m.start() < f and i0 < m.end() for i0, f, _ in escolhidos):
                continue
            escolhidos.append((m.start(), m.end(), marcado))
            break
    for ini, fim, marcado in sorted(escolhidos, reverse=True):
        html = html[:ini] + marcado + html[fim:]
    return html


_BLOCO = re.compile(r"<(?:p|h1|h3|table)(?=[\s>])")


def _blocos(html: str) -> list[tuple[int, int]]:
    """Intervalos (inicio, fim) dos paragrafos/titulos/tabelas do html do contrato."""
    ini = [m.start() for m in _BLOCO.finditer(html)]
    return list(zip(ini, ini[1:] + [len(html)]))


def _html_honorarios(escopos: list, acessorios) -> str:
    import tempfile

    data = ContratoRequest(
        contratantes=[_CONTRATANTE_PREVIA],
        escopos=escopos,
        acessorios=acessorios or Acessorios(),
        participacao={"tem_participacao": False},
    )
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        get_generator()._build_document(data).save(str(tmp_path))
        html = _docx_to_html(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
    # Secoes saem como <h3> numerado; recorta da secao 3 ate a seguinte.
    inicio = html.rfind("<h3>", 0, html.find("OUTRAS DISPOSIÇÕES SOBRE HONORÁRIOS"))
    fim = html.rfind("<h3>", 0, html.find("CLÁUSULAS GERAIS"))
    return html[inicio:fim]


def _tirar_texto(obj, texto: str):
    """Copia do dump com todo valor igual a `texto` esvaziado."""
    if isinstance(obj, dict):
        return {k: _tirar_texto(v, texto) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_tirar_texto(v, texto) for v in obj]
    return "" if obj == texto else obj


def _trechos_do_campo(html: str, body: "PreviaHonorariosRequest", texto: str) -> list[tuple[int, int]] | None:
    """Onde o gerador escreveu o campo: gera o contrato de novo sem o texto e fica com
    os blocos que sumiram ou mudaram. Falhou = None (sem destaque, nunca no lugar errado;
    o campo continua indo a IA)."""
    from collections import Counter

    try:
        sem = body.model_dump(mode="json")
        sem = PreviaHonorariosRequest(**_tirar_texto(sem, texto))
        html_sem = _html_honorarios(sem.escopos, sem.acessorios)
    except Exception:
        logger.warning("Previa: nao foi possivel localizar o campo no contrato", exc_info=True)
        return None
    restam = Counter(html_sem[i:f] for i, f in _blocos(html_sem))
    spans = []
    for i, f in _blocos(html):
        if restam[html[i:f]] > 0:
            restam[html[i:f]] -= 1
        else:
            spans.append((i, f))
    return spans


@router.post("/preview-honorarios")
def preview_honorarios(
    body: PreviaHonorariosRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Previa so' da secao de honorarios, para o pop-up do wizard: o texto digitado
    vem destacado e, com revisar=True, a correcao da IA aparece no lugar. Nada e' gravado."""
    from app.utils.currency import percentual_com_extenso

    html = _html_honorarios(body.escopos, body.acessorios)

    dump = {"escopos": [e.model_dump(mode="json") for e in body.escopos]}
    # O gerador tira a pontuacao final do que foi digitado; o destaque tem de casar.
    completos = contract_reviewer.campos_abertos(dump)
    # O contrato pode escrever o texto diferente do digitado (inicial, ponto final,
    # espacos); a busca no html e o destaque usam o texto como saiu no contrato.
    # Cada campo so' vale dentro dos blocos onde o gerador o escreveu.
    trechos: dict = {}
    como_sai = []
    for c in completos:
        if c[1] not in trechos:
            trechos[c[1]] = _trechos_do_campo(html, body, c[1])
        sp = trechos[c[1]]
        if sp is None:
            # nao deu para localizar: o campo vai a IA (procurado no html todo), sem destaque
            como_sai.append((c, _achar_no_html(html, c[1], destaque=False), None, []))
            continue
        regiao = "".join(html[i:f] for i, f in sp)
        como_sai.append((c, _achar_no_html(regiao, c[1], destaque=False), _achar_no_html(regiao, c[1]), sp))
    # Vai a IA o que foi escrito no contrato; so' recebe destaque o que se acha sem duvida.
    completos = [c for c, escrito, _, _ in como_sai if escrito and len(escrito) >= 3]
    textos: list = [(achado, sp) for _, _, achado, sp in como_sai if achado and len(achado) >= 3]
    # Desconto percentual nao e' texto livre, mas e' a "especificacao" que a pessoa preencheu.
    for h in (e.model_dump(mode="json").get(k) or {} for e in body.escopos for k in contract_reviewer.HONORARIO_ROTULOS):
        if h.get("tem_desconto") and h.get("desconto_tipo") != "livre" and h.get("desconto_percentual"):
            textos.append(percentual_com_extenso(h["desconto_percentual"]))

    findings: list[dict] = []
    avisos: list[dict] = []
    erro = None
    if body.revisar and completos and not contract_reviewer.is_configured():
        # Sem isto o pop-up dizia "nenhuma correção necessária" sem a IA ter olhado nada.
        erro = "Revisão da IA não configurada neste ambiente (DEEPSEEK_API_KEY)."
    elif body.revisar and completos:
        try:
            # Cada campo vai com a frase fixa do contrato em volta (so' contexto: a
            # correcao tem de cair dentro do que foi digitado — so_do_digitado garante).
            achados = contract_reviewer.so_do_digitado(
                contract_reviewer.review_text(
                    contract_reviewer.texto_para_revisao(completos), avisar_ambiguidade=True
                ),
                dump,
            )
            findings = [f for f in achados if f.get("tipo") != "aviso"]
            avisos = [f for f in achados if f.get("tipo") == "aviso"]
        except contract_reviewer.ContractReviewError as e:
            logger.warning("Revisao da previa de honorarios indisponivel: %s", e)
            erro = "Revisão da IA indisponível."
    return {
        "html": _marcar_digitados(html, textos, findings),
        "findings": findings,
        "avisos": avisos,
        "erro": erro,
    }


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
    if user.role != "admin" and contract.created_by != user.email:
        raise HTTPException(403, "Sem permissao")

    from app.routers.docuseal import _resolve_contract_filepath

    filepath = _resolve_contract_filepath(contract_id, db)
    return HTMLResponse(_docx_to_html(Path(filepath)))
