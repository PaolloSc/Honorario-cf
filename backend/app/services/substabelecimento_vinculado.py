"""Regras de substabelecimento que atravessam mais de uma rota (issue #126).

- Quando o substabelecimento nasce de um distrato, o vinculo fica no form_data
  (`distrato_origem_id`), sem coluna nova: editar o distrato regera o substabelecimento.
- Um substabelecimento ja enviado para assinatura ou assinado nao e' alterado: um novo e' criado.
- Novo processo do mesmo outorgante (mesmo CPF/CNPJ) e' acrescentado ao substabelecimento existente.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import AuditLogDB, ContractDB, ContractVersionDB, serialize_cliente_docs, utcnow
from app.models.documentos_complementares import (
    ROTULO_DOCUMENTO,
    TIPO_SUBSTABELECIMENTO,
    DistratoRequest,
    Processo,
    SubstabelecimentoRequest,
    email_contato,
    nome_contratante,
    nome_exibicao,
)
from app.services.contract_dispatch import get_generator

MOTIVO_TRAVADO = "o substabelecimento existente já foi enviado para assinatura ou assinado e não pode ser alterado"


def so_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def documento_do_outorgante(form: dict) -> str:
    """CPF/CNPJ (so digitos) do outorgante de um substabelecimento salvo; '' se nao informado."""
    o = form.get("outorgante") or {}
    return so_digitos(o.get("cnpj") or o.get("cpf"))


def form_data_atual(contract: ContractDB, db: Session) -> dict:
    ver = (
        db.query(ContractVersionDB)
        .filter(
            ContractVersionDB.contract_id == contract.contract_id,
            ContractVersionDB.version_number == contract.current_version,
        )
        .first()
    )
    return json.loads(ver.form_data_json) if ver else {}


def travado(contract: ContractDB, db: Session) -> bool:
    """Ja foi enviado para assinatura (ou assinado): nao se mexe mais no documento."""
    if contract.status in ("enviado", "assinado"):
        return True
    return (
        db.query(ContractVersionDB)
        .filter(ContractVersionDB.contract_id == contract.contract_id, ContractVersionDB.docuseal_submission_id.isnot(None))
        .first()
        is not None
    )


def _numero_normalizado(numero: str) -> str:
    return re.sub(r"[^0-9a-z]", "", numero.lower())


def acrescentar_processos(existentes: list[Processo], novos: list[Processo]) -> list[Processo]:
    """Existentes + os novos que ainda nao constam (mesmo numero, ignorando pontuacao)."""
    vistos = {_numero_normalizado(p.numero) for p in existentes}
    saida = list(existentes)
    for p in novos:
        chave = _numero_normalizado(p.numero)
        if chave not in vistos:
            vistos.add(chave)
            saida.append(p)
    return saida


def substabelecimentos_do_outorgante(db: Session, documento: str) -> list[ContractDB]:
    """Substabelecimentos validos (nao cancelados) do outorgante, do mais novo ao mais antigo."""
    if len(documento) not in (11, 14):
        return []
    candidatos = (
        db.query(ContractDB)
        .filter(ContractDB.tipo_contrato == TIPO_SUBSTABELECIMENTO, ContractDB.status != "cancelado")
        .order_by(ContractDB.created_at.desc(), ContractDB.id.desc())
        .all()
    )
    return [c for c in candidatos if documento_do_outorgante(form_data_atual(c, db)) == documento]


def nova_versao(db: Session, contract: ContractDB, data: SubstabelecimentoRequest, user_email: str, motivo: str) -> str:
    """Regera o DOCX do mesmo documento e grava a proxima versao (sem commit). Devolve o arquivo."""
    _, filepath = get_generator(TIPO_SUBSTABELECIMENTO).generate(data, contract_id=contract.contract_id)
    numero = contract.current_version + 1
    db.add(ContractVersionDB(
        contract_id=contract.contract_id,
        version_number=numero,
        form_data_json=json.dumps(data.model_dump(mode="json"), ensure_ascii=False),
        file_path=str(filepath),
        created_by=user_email,
        created_at=utcnow(),
    ))
    contract.current_version = numero
    contract.client_name = nome_exibicao(data)
    contract.client_email = email_contato(data)
    contract.status = "rascunho"
    contract.updated_by = user_email
    contract.updated_at = utcnow()
    db.add(AuditLogDB(
        contract_id=contract.contract_id, action="edicao", version_number=numero, user_email=user_email,
        detail=f"Nova versão {numero} gerada: {motivo}", created_at=utcnow(),
    ))
    return str(filepath)


def gravar_novo(db: Session, tipo: str, data, origem: ContractDB | None, user_email: str) -> tuple[str, str]:
    """Gera o DOCX e grava contrato, versao 1 e auditoria (sem commit). Devolve (contract_id, arquivo)."""
    contract_id, filepath = get_generator(tipo).generate(data)
    try:
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
            created_by=user_email,
            updated_by=user_email,
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
            created_by=user_email,
            created_at=utcnow(),
        ))
        rotulo = ROTULO_DOCUMENTO[tipo]
        db.add(AuditLogDB(
            contract_id=contract_id, action="criacao", version_number=1, user_email=user_email,
            detail=f"{rotulo} gerado para {nome}", created_at=utcnow(),
        ))
        if origem_id:
            db.add(AuditLogDB(
                contract_id=origem_id, action="documento_complementar", user_email=user_email,
                detail=f"{rotulo} criado ({contract_id})", created_at=utcnow(),
            ))
    except Exception:
        Path(filepath).unlink(missing_ok=True)  # nada de .docx sem registro
        raise
    return contract_id, filepath


def substabelecimento_do_distrato(distrato: DistratoRequest, distrato_id: str) -> SubstabelecimentoRequest:
    """Substabelecimento sem reserva a favor do novo patrono, preenchido com o contrato e o distrato."""
    d = distrato.substabelecimento
    nomes = [nome_contratante(c) for c in distrato.contratantes] or ["o CONTRATANTE"]
    primeiro = distrato.contratantes[0] if distrato.contratantes else {}
    if len(distrato.contratantes) == 1 and primeiro.get("cnpj"):
        outorgante = {"razao_social": nomes[0], "cnpj": primeiro["cnpj"]}
    elif len(distrato.contratantes) == 1:
        outorgante = {"nome": nomes[0], "cpf": primeiro.get("cpf") or None}
    else:  # varios contratantes: o texto cita todos, sem documento
        outorgante = {"nome": " e ".join(nomes)}
    return SubstabelecimentoRequest(
        contrato_origem_id=distrato.contrato_origem_id,
        distrato_origem_id=distrato_id,
        data_documento=distrato.data_documento,
        outorgante=outorgante,
        substabelecentes=d.substabelecentes,
        substabelecidos=d.substabelecidos,
        endereco_substabelecidos=d.endereco_substabelecidos,
        processos=d.processos,
    )


def sincronizar_do_distrato(
    db: Session, distrato: ContractDB, form_distrato: dict, user_email: str
) -> tuple[list[str], list[str], list[str]]:
    """Depois de editar um distrato, mantem o substabelecimento que nasceu dele em dia.

    Devolve (regerados, criados, arquivos_novos). Distrato sem substabelecimento vinculado
    (salvo antes da opcao) nao gera nada. Vinculado ja enviado/assinado: cria um novo.
    """
    data = DistratoRequest(**form_distrato)
    if not (data.substabelecer_e_devolver and data.substabelecimento):
        return [], [], []
    vinculados = [
        c for c in db.query(ContractDB)
        .filter(
            ContractDB.contrato_origem_id == distrato.contrato_origem_id,
            ContractDB.tipo_contrato == TIPO_SUBSTABELECIMENTO,
            ContractDB.status != "cancelado",
        )
        .order_by(ContractDB.created_at.desc(), ContractDB.id.desc())
        .all()
        if form_data_atual(c, db).get("distrato_origem_id") == distrato.contract_id
    ]
    if not vinculados:
        return [], [], []
    atual = vinculados[0]
    novo = substabelecimento_do_distrato(data, distrato.contract_id)
    salvo = SubstabelecimentoRequest(**form_data_atual(atual, db)).model_dump(mode="json")
    if salvo == novo.model_dump(mode="json"):
        return [], [], []
    if travado(atual, db):
        origem = db.query(ContractDB).filter(ContractDB.contract_id == distrato.contrato_origem_id).first()
        cid, arquivo = gravar_novo(db, TIPO_SUBSTABELECIMENTO, novo, origem, user_email)
        return [], [cid], [arquivo]
    nova_versao(db, atual, novo, user_email, "distrato de origem alterado")
    return [atual.contract_id], [], []
