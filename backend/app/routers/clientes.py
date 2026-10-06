"""Sugestão de cliente recorrente para o Step 1 do wizard.

Exceção consciente à regra "advogado só vê os próprios contratos": qualquer
advogado logado acha o cliente que outro já atendeu (decisão do escritório,
06/10/2026). Em troca, devolve SÓ a qualificação do contratante, montada por
lista branca: nada de escopo, honorário, valor, cláusula nem id/link do
contrato de origem — só a data dele, para a pessoa saber o quão velho é o dado.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import ContractDB, ContractVersionDB, get_db
from app.utils.documento import normalizar_doc

router = APIRouter(prefix="/api/clientes", tags=["Clientes"])

LIMITE_SUGESTOES = 10
# Contratos lidos por busca; no volume do escritório cobre de sobra os 10 clientes.
LIMITE_CONTRATOS = 100

CAMPOS_PF = ("tipo", "nome", "nacionalidade", "cpf", "profissao", "estado_civil", "endereco", "email", "whatsapp")
CAMPOS_PJ = ("tipo", "cnpj", "razao_social", "endereco", "email", "whatsapp")
CAMPOS_REPRESENTANTE = ("nome", "nacionalidade", "cpf", "profissao", "estado_civil", "email", "whatsapp")


class Sugestao(BaseModel):
    documento: str
    nome: str
    data_contrato: str
    contratante: dict


class SugestoesResponse(BaseModel):
    sugestoes: list[Sugestao]


def _pegar(origem: dict, campos: tuple[str, ...]) -> dict:
    return {k: origem[k] for k in campos if isinstance(origem.get(k), str)}


def _qualificacao(c: dict) -> dict:
    """Lista branca: só o que vai no card do contratante."""
    if c.get("tipo") == "PJ":
        out = _pegar(c, CAMPOS_PJ)
        if "cnpj" in out:
            # Contrato legado guardou com máscara; o form (e o mapa da Receita/QSA) usa sem.
            out["cnpj"] = normalizar_doc(out["cnpj"])
        reps = c.get("representantes")
        if not reps and c.get("representante_nome"):
            # Legado: representante único em campos soltos.
            reps = [{k: c.get(f"representante_{k}") for k in CAMPOS_REPRESENTANTE}]
        out["representantes"] = [_pegar(r, CAMPOS_REPRESENTANTE) for r in reps or [] if isinstance(r, dict)]
        return out
    return _pegar(c, CAMPOS_PF)


@router.get("/sugestoes", response_model=SugestoesResponse)
def sugestoes(
    q: str = Query(..., min_length=3, max_length=100),
    _user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    termo = q.strip().casefold()
    doc_q = normalizar_doc(q)
    # ponytail: nome só bate no 1º contratante (client_name) e com o acento igual; os
    # demais contratantes são achados pelo CPF/CNPJ. Busca no form_data se fizer falta.
    filtro = ContractDB.client_name.ilike(f"%{q.strip()}%")
    if len(doc_q) >= 3:
        filtro = filtro | ContractDB.cliente_docs.like(f"%{doc_q}%")

    # Sem filtro por created_by de propósito (ver docstring do módulo).
    linhas = (
        db.query(ContractVersionDB.form_data_json, ContractVersionDB.created_at)
        .select_from(ContractDB)
        .join(ContractVersionDB, (ContractVersionDB.contract_id == ContractDB.contract_id)
              & (ContractVersionDB.version_number == ContractDB.current_version))
        .filter(filtro)
        .order_by(ContractDB.updated_at.desc())
        .limit(LIMITE_CONTRATOS)
        .all()
    )

    vistos: set[str] = set()
    out: list[Sugestao] = []
    for form_json, criado_em in linhas:
        try:
            contratantes = json.loads(form_json).get("contratantes") or []
        except (ValueError, AttributeError):
            continue
        for c in contratantes:
            if not isinstance(c, dict):
                continue
            doc = normalizar_doc(c.get("cnpj") or c.get("cpf"))
            nome = (c.get("razao_social") or c.get("nome") or "").strip()
            if not doc or doc in vistos:
                continue
            if termo not in nome.casefold() and not (len(doc_q) >= 3 and doc_q in doc):
                continue
            vistos.add(doc)
            out.append(Sugestao(documento=doc, nome=nome, data_contrato=criado_em.isoformat(), contratante=_qualificacao(c)))
            if len(out) >= LIMITE_SUGESTOES:
                return SugestoesResponse(sugestoes=out)
    return SugestoesResponse(sugestoes=out)
