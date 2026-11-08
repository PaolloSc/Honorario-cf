"""Assinatura: enviar um contrato para assinatura no DocuSeal.

Caso de uso sem HTTP. A rota (routers/docuseal.py) so traduz: EnvioInvalido -> 400,
ArquivoNaoEncontrado -> 404 e o resto -> 500. Aqui ficam as regras: quem assina pelo
escritorio, testemunha fixa, papeis unicos, ordem de assinatura, DOCX com os campos
de assinatura, reenvio e trilha de auditoria.

`docuseal` e' o seam: producao usa o cliente real; teste passa um falso, sem patchar a rota.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import ColaboradorDB, ContractDB, ContractVersionDB, utcnow
from app.models.documentos_complementares import ROTULO_DOCUMENTO
from app.services import servicos_externos
from app.services.arquivo_contrato import resolve_backend_path, resolver_arquivo
from app.services.ciclo_contrato import registrar_auditoria
from app.services.contrato_carregado import carregar_versao, tipo_da_versao

logger = logging.getLogger(__name__)


class EnvioInvalido(Exception):
    """Pedido de envio que viola uma regra de assinatura (a rota responde 400)."""


@dataclass
class ResultadoEnvio:
    success: bool
    message: str
    submission_id: str | None = None
    # Submitters "Contratante*" como o DocuSeal devolveu; a rota decide o que a tela mostra.
    contratantes: list[dict[str, Any]] = field(default_factory=list)


def _patch_docx_with_signatures(
    existing_filepath: Path,
    signatarios: list[dict],
    contract_id: str,
    db: Session,
    latest_ver,
) -> Path:
    """Patch an existing DOCX to ensure it has signature fields for all signatarios.

    If the existing file can be read, appends missing signature fields.
    If not, creates a new DOCX with all signature fields.
    """
    from docx import Document

    output_dir = resolve_backend_path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"contrato_{contract_id}.docx"

    # Try to open existing file and patch it
    doc = None
    if existing_filepath.exists():
        try:
            doc = Document(str(existing_filepath))
        except Exception:
            pass

    if doc is None:
        # Create a new minimal document
        doc = Document()
        doc.add_paragraph("CONTRATO DE PRESTACAO DE SERVICOS ADVOCATICIOS")
        doc.add_paragraph()
        doc.add_paragraph("(Documento regenerado para assinatura digital)")
        doc.add_paragraph()

    # Check if signature fields already exist for all roles
    full_text = "\n".join(p.text for p in doc.paragraphs)
    missing_sigs = []
    for sig in signatarios:
        role = sig.get("role", "")
        if f";type=signature;role={role}" not in full_text:
            missing_sigs.append(sig)

    if missing_sigs:
        # Append signature fields at the end
        if len(doc.paragraphs) > 3:
            doc.add_paragraph()
            doc.add_paragraph("_" * 70)
            doc.add_paragraph()

        # Add ALL signature fields to ensure consistency
        contratado_sigs = [s for s in signatarios if s.get("role", "").startswith("Contratado")]
        contratante_sigs = [s for s in signatarios if s.get("role", "").startswith("Contratante")]

        for sig in contratado_sigs:
            role = sig["role"]
            name = sig.get("contratado_nome") or sig.get("name", "Contratado")
            doc.add_paragraph(f"{{{{Assinatura {name};type=signature;role={role}}}}}")
            doc.add_paragraph(f"CONTRATADO: {name.upper()}")
            doc.add_paragraph()

        for sig in contratante_sigs:
            role = sig["role"]
            name = sig.get("name", "Contratante")
            doc.add_paragraph(f"{{{{Assinatura {name};type=signature;role={role}}}}}")
            doc.add_paragraph(f"CONTRATANTE: {name.upper()}")
            doc.add_paragraph()

    doc.save(str(output_path))

    # Update DB
    if latest_ver:
        latest_ver.file_path = str(output_path)
        db.commit()

    logger.info("Patched DOCX with %d signature fields at: %s", len(signatarios), output_path)
    return output_path


ESCRITORIO_NOME = "Carvalho & Furtado Advogados"


def _resolver_assinatura_escritorio(signatarios: list[dict], db: Session) -> list[dict]:
    """Todo contrato de honorarios tem exatamente uma assinatura pelo escritorio
    (papel "Contratado"), dada por um socio ativo do roster — advogado nao-socio
    nao representa o C&F.
    """
    escritorio = [s for s in signatarios if s.get("role") == "Contratado"]
    if len(escritorio) != 1:
        raise EnvioInvalido("Escolha o sócio que assina pelo escritório.")
    socio = escritorio[0]
    email = (socio.get("email") or "").strip().lower()
    eh_socio = email and db.query(ColaboradorDB).filter(
        func.lower(ColaboradorDB.email) == email,
        ColaboradorDB.papel == "socio",
        ColaboradorDB.ativo.is_(True),
    ).first()
    if not eh_socio:
        raise EnvioInvalido("Só um sócio ativo pode assinar pelo escritório.")

    socio["contratado_nome"] = ESCRITORIO_NOME
    return signatarios


def _nome_testemunha1(db: Session) -> str:
    """Nome da Testemunha 1 fixa, com o cadastro mandando na variavel de ambiente.

    O nome vivia so' em TESTEMUNHA1_NOME e divergiu do roster de colaboradores:
    o contrato saiu assinado com o sobrenome errado durante meses. Pior, corrigir
    exigia deploy, e um valor velho no ambiente calava o default do codigo.

    Agora o cadastro (editavel em /admin/colaboradores) e' a fonte, e a config
    fica so' de reserva para quando a pessoa nao estiver no roster.
    """
    colaborador = (
        db.query(ColaboradorDB)
        .filter(
            func.lower(ColaboradorDB.email) == settings.testemunha1_email.lower(),
            ColaboradorDB.ativo.is_(True),
        )
        .first()
    )
    if not colaborador or not colaborador.nome:
        return settings.testemunha1_nome

    if colaborador.nome != settings.testemunha1_nome:
        # Divergencia visivel em vez de silenciosa: o cadastro vence, mas fica
        # registrado que TESTEMUNHA1_NOME esta' desatualizado no ambiente.
        logger.warning(
            "TESTEMUNHA1_NOME (%r) diverge do cadastro (%r) para %s; usando o cadastro",
            settings.testemunha1_nome,
            colaborador.nome,
            settings.testemunha1_email,
        )
    return colaborador.nome


async def enviar(
    db: Session,
    contract_id: str,
    signatarios: list[dict[str, str]],
    user_email: str,
    docuseal=None,
) -> ResultadoEnvio:
    """Envia a ultima versao do contrato para assinatura."""
    service = docuseal or servicos_externos.get_docuseal_service()

    latest_ver = (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract_id)
        .order_by(ContractVersionDB.version_number.desc())
        .first()
    )
    from app.models.contrato_consumidor import TIPO_CONSUMIDOR_AEREO
    from app.models.documentos_complementares import TIPO_SUBSTABELECIMENTO
    from app.services.consumidor_generator import CONTRATADA_NOME

    tipo = tipo_da_versao(latest_ver.form_data_json if latest_ver else None)
    eh_consumidor = tipo == TIPO_CONSUMIDOR_AEREO
    eh_substabelecimento = tipo == TIPO_SUBSTABELECIMENTO

    # Build the full list of signatarios first (need roles to regenerate DOCX)
    all_signatarios = list(signatarios)

    # Contrato de consumidor: "Contratado" e' sempre a Monica por nome/CPF/OAB
    # (CONTRATADA_NOME/CPF/OAB fixos), entao segue com submitter proprio.
    if eh_consumidor:
        if not any(s.get("role") == "Contratado" for s in all_signatarios):
            all_signatarios.append({
                "email": settings.cf_signer_email,
                "name": CONTRATADA_NOME,
                "role": "Contratado",
            })
    elif eh_substabelecimento:
        # So' os substabelecentes assinam: sem socio "Contratado", contratante nem testemunha.
        if not all_signatarios or any(
            not s.get("role", "").startswith("Substabelecente") for s in all_signatarios
        ):
            raise EnvioInvalido("O substabelecimento é assinado apenas pelos substabelecentes.")
    else:
        all_signatarios = _resolver_assinatura_escritorio(all_signatarios, db)

    # Testemunha 1 fixa (financeiro): injetada em toda submissao.
    # Inserida ANTES de eventuais testemunhas do payload p/ que a dedup a nomeie "Testemunha 1".
    lilian_present = eh_substabelecimento or any(
        s.get("email", "").lower() == settings.testemunha1_email.lower()
        and s.get("role", "").startswith("Testemunha")
        for s in all_signatarios
    )
    if not lilian_present:
        first_testemunha_idx = next(
            (i for i, s in enumerate(all_signatarios) if s.get("role", "").startswith("Testemunha")),
            len(all_signatarios),
        )
        all_signatarios.insert(first_testemunha_idx, {
            "email": settings.testemunha1_email,
            "name": _nome_testemunha1(db),
            "role": "Testemunha",
        })

    # Deduplicate roles: DocuSeal requires unique role per submitter
    # and each role must match a signature field in the template
    role_counts = Counter(s.get("role", "Contratante") for s in all_signatarios)
    role_indices: dict[str, int] = {}
    for sig in all_signatarios:
        role = sig.get("role", "Contratante")
        if role_counts[role] > 1:
            role_indices[role] = role_indices.get(role, 0) + 1
            sig["role"] = f"{role} {role_indices[role]}"

    # Assign order for sequential signing:
    # Contratante(s) -> Contratado (C&F) -> Testemunha(s) -> Lilian por ultimo
    _ROLE_ORDER = {"Contratante": 1, "Substabelecente": 1, "Contratado": 3, "Testemunha": 4}
    for sig in all_signatarios:
        # Extract base role (without number suffix) for order lookup
        base_role = sig.get("role", "Contratante").rstrip(" 0123456789")
        sig["order"] = _ROLE_ORDER.get(base_role, 1)
        # Lilian (financeiro) so recebe o documento quando todos ja assinaram
        if (
            base_role == "Testemunha"
            and sig.get("email", "").lower() == settings.testemunha1_email.lower()
        ):
            sig["order"] = 5
    # DocuSeal ("order": "preserved") sequencia pela POSICAO no array, nao pelo
    # campo "order" — sem este sort a Lilian receberia o documento antes da hora.
    all_signatarios.sort(key=lambda s: s["order"])

    # Regenerate DOCX with signature fields matching the unique signatario roles
    filepath = resolver_arquivo(contract_id, db)

    if latest_ver and latest_ver.form_data_json:
        try:
            carregado = carregar_versao(latest_ver)
            _, new_filepath = carregado.gerador.generate(
                carregado.request,
                contract_id=contract_id,
                signatario_roles=all_signatarios,
            )
            filepath = Path(new_filepath)
            latest_ver.file_path = str(filepath)
            db.commit()
            logger.info("Regenerated DOCX with matching signature roles for contract %s", contract_id)
        except Exception as regen_err:
            logger.warning("Full regeneration failed: %s. Patching DOCX with signature fields.", regen_err)
            # Fallback: patch the existing DOCX or create a new one with signature fields
            try:
                filepath = _patch_docx_with_signatures(filepath, all_signatarios, contract_id, db, latest_ver)
            except Exception as patch_err:
                logger.error("Failed to patch DOCX with signatures: %s", patch_err)

    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    rotulo = ROTULO_DOCUMENTO.get(
        tipo,
        "Contrato de Prestação de Serviços" if eh_consumidor else "Contrato Honorários",
    )
    template_name = (
        f"{rotulo} — {contract.client_name}"
        if contract and contract.client_name
        else f"{rotulo} {contract_id}"
    )
    result = await service.create_template_from_docx(
        filepath=str(filepath),
        name=template_name,
    )

    template_id = result.get("id")
    if not template_id:
        return ResultadoEnvio(success=False, message="Failed to create DocuSeal template")

    sign_result = await service.send_for_signature(
        template_id=template_id,
        signatarios=all_signatarios,
        send_email=True,
    )

    if sign_result.get("success"):
        submission = sign_result.get("submission", {})
        submission_id = submission.get("id")

        # Reenvio: arquiva as submissoes anteriores ainda abertas, senao o
        # cliente fica com dois links validos e pode assinar a versao velha.
        if contract and contract.status in ("enviado", "recusado"):
            anteriores = {
                v.docuseal_submission_id
                for v in contract.versions
                if v.docuseal_submission_id and v.docuseal_submission_id != str(submission_id)
            }
            for antiga in sorted(anteriores):
                try:
                    await service.archive_submission(antiga)
                except Exception as e:  # nao impede o envio novo
                    logger.warning("Nao arquivou a submissao antiga %s: %s", antiga, e)

        # Update DB: status + audit log
        if contract:
            contract.status = "enviado"
            contract.updated_at = utcnow()
            if latest_ver:
                latest_ver.docuseal_submission_id = str(submission_id) if submission_id else None
            registrar_auditoria(db, contract_id, "envio_assinatura", f"Enviado para assinatura via DocuSeal (submission {submission_id})", contract.current_version, user_email)
            db.commit()

        # Nada e' enviado ao financeiro neste momento. A ficha de participacao
        # so vai ao financeiro quando TODAS as partes assinarem (webhook
        # submission.completed). Lilian (financeiro) recebe o contrato como
        # Testemunha 1 via DocuSeal.

        return ResultadoEnvio(
            success=True,
            message="Documento enviado para assinatura com sucesso",
            submission_id=str(submission_id) if submission_id else None,
            contratantes=[
                s for s in submission.get("submitters") or []
                if s.get("role", "").startswith("Contratante")
            ],
        )
    else:
        return ResultadoEnvio(success=False, message=sign_result.get("message", "Erro ao enviar para assinatura"))


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
