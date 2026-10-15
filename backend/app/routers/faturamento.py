"""Cadastros da emissao de NFS-e e faturas: servicos, tomadores, quem fatura o contrato e faturas.

Tudo aqui e so para o papel financeiro (ou admin). Nao emite nada: emitir e outra PR. Fatura so
nasce a mao nesta etapa; a aprovacao e o ato que libera a emissao."""
from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_financeiro
from app.database import ContractDB, ContractVersionDB, get_db
from app.models.emissao_db import ContratoFaturamentoDB, FaturaDB, ServicoDB, TomadorDB
from app.utils.documento import normalizar_doc

router = APIRouter(prefix="/api", tags=["faturamento"])


def _digitos(v: str | None) -> str | None:
    return re.sub(r"\D", "", v) if v else v


def _nbs_9(v: str | None) -> str | None:
    d = _digitos(v)  # aceita 1.1301.90.00
    if d and len(d) != 9:
        raise ValueError("NBS tem 9 digitos")
    return d or None


def _cep_8(v: str | None) -> str | None:
    d = _digitos(v)
    if d and len(d) != 8:
        raise ValueError("CEP tem 8 digitos")
    return d or None


# --- serviços -------------------------------------------------------------------

class ServicoIn(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    descricao_padrao: str = Field(default="Referente a serviços advocatícios", min_length=1)
    codigo_lc116: str | None = Field(default=None, max_length=10)
    c_trib_nac: str = Field(pattern=r"^\d{6}$")
    c_trib_mun: str | None = Field(default=None, pattern=r"^\d{3}$")
    nbs: str | None = None
    aliquota_iss: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    iss_retido_padrao: bool = False
    incluir_ibscbs: bool = False
    c_ind_op: str | None = Field(default=None, pattern=r"^\d{6}$")
    cst_ibscbs: str | None = Field(default=None, pattern=r"^\d{3}$")
    c_class_trib: str | None = Field(default=None, pattern=r"^\d{6}$")
    tax_code_id: int | None = None
    ativo: bool = True

    _nbs = field_validator("nbs")(lambda cls, v: _nbs_9(v))


class ServicoPatch(BaseModel):
    """Campos opcionais: so o que vier e alterado."""
    model_config = ConfigDict(extra="forbid")
    nome: str | None = Field(default=None, min_length=1, max_length=100)
    descricao_padrao: str | None = Field(default=None, min_length=1)
    codigo_lc116: str | None = Field(default=None, max_length=10)
    c_trib_nac: str | None = Field(default=None, pattern=r"^\d{6}$")
    c_trib_mun: str | None = Field(default=None, pattern=r"^\d{3}$")
    nbs: str | None = None
    aliquota_iss: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    iss_retido_padrao: bool | None = None
    incluir_ibscbs: bool | None = None
    c_ind_op: str | None = Field(default=None, pattern=r"^\d{6}$")
    cst_ibscbs: str | None = Field(default=None, pattern=r"^\d{3}$")
    c_class_trib: str | None = Field(default=None, pattern=r"^\d{6}$")
    tax_code_id: int | None = None
    ativo: bool | None = None

    _nbs = field_validator("nbs")(lambda cls, v: _nbs_9(v))


class ServicoOut(ServicoIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


def _exigir_ibscbs_completo(s: ServicoDB) -> None:
    if s.incluir_ibscbs and not (s.c_ind_op and s.cst_ibscbs and s.c_class_trib):
        raise HTTPException(400, "Com IBS/CBS, informe c_ind_op, cst_ibscbs e c_class_trib")


@router.get("/servicos", response_model=list[ServicoOut])
def listar_servicos(todos: bool = False, db: Session = Depends(get_db), _u: CurrentUser = Depends(require_financeiro)):
    q = db.query(ServicoDB)
    if not todos:
        q = q.filter(ServicoDB.ativo.is_(True))
    return q.order_by(ServicoDB.nome).all()


@router.post("/servicos", response_model=ServicoOut, status_code=201)
def criar_servico(body: ServicoIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require_financeiro)):
    s = ServicoDB(**body.model_dump(), criado_por=user.email)
    _exigir_ibscbs_completo(s)
    db.add(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ja existe um servico com esse nome") from None
    return s


@router.patch("/servicos/{servico_id}", response_model=ServicoOut)
def alterar_servico(servico_id: int, body: ServicoPatch, db: Session = Depends(get_db),
                    _u: CurrentUser = Depends(require_financeiro)):
    s = db.get(ServicoDB, servico_id)
    if s is None:
        raise HTTPException(404, "Servico nao encontrado")
    for campo, valor in body.model_dump(exclude_unset=True).items():
        if valor is None and campo in ("nome", "descricao_padrao", "c_trib_nac", "iss_retido_padrao", "incluir_ibscbs", "ativo"):
            raise HTTPException(400, f"{campo} nao pode ser vazio")
        setattr(s, campo, valor)
    _exigir_ibscbs_completo(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ja existe um servico com esse nome") from None
    return s


# --- tomadores ------------------------------------------------------------------

class TomadorIn(BaseModel):
    documento: str
    nome: str = Field(min_length=1, max_length=256)
    emails: list[str] = Field(default_factory=list)
    inscricao_municipal: str | None = Field(default=None, max_length=30)
    optante_simples: bool = False
    orgao_publico: bool = False
    cep: str | None = None
    logradouro: str | None = Field(default=None, max_length=256)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=120)
    bairro: str | None = Field(default=None, max_length=120)
    municipio_ibge: str | None = Field(default=None, pattern=r"^\d{7}$")
    uf: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")

    @field_validator("documento")
    @classmethod
    def _doc(cls, v):
        d = normalizar_doc(v)
        if len(d) not in (11, 14):
            raise ValueError("CPF tem 11 e CNPJ tem 14 caracteres")
        return d

    _cep = field_validator("cep")(lambda cls, v: _cep_8(v))


class TomadorPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str | None = Field(default=None, min_length=1, max_length=256)
    emails: list[str] | None = None
    inscricao_municipal: str | None = Field(default=None, max_length=30)
    optante_simples: bool | None = None
    orgao_publico: bool | None = None
    cep: str | None = None
    logradouro: str | None = Field(default=None, max_length=256)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=120)
    bairro: str | None = Field(default=None, max_length=120)
    municipio_ibge: str | None = Field(default=None, pattern=r"^\d{7}$")
    uf: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    ativo: bool | None = None

    _cep = field_validator("cep")(lambda cls, v: _cep_8(v))


class TomadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    documento: str
    nome: str
    emails: list[str]
    inscricao_municipal: str | None
    optante_simples: bool
    orgao_publico: bool
    cep: str | None
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    municipio_ibge: str | None
    uf: str | None
    origem: str
    ativo: bool


@router.get("/tomadores", response_model=list[TomadorOut])
def listar_tomadores(q: str | None = Query(default=None, max_length=100), db: Session = Depends(get_db),
                     _u: CurrentUser = Depends(require_financeiro)):
    query = db.query(TomadorDB).filter(TomadorDB.ativo.is_(True))
    if q and q.strip():
        doc = normalizar_doc(q)
        filtro = TomadorDB.nome.ilike(f"%{q.strip()}%")
        query = query.filter(filtro | TomadorDB.documento.like(f"%{doc}%") if len(doc) >= 3 else filtro)
    return query.order_by(TomadorDB.nome).limit(200).all()


def _gravar_tomador(db: Session, t: TomadorDB) -> TomadorDB:
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ja existe um tomador com esse documento") from None
    return t


@router.post("/tomadores", response_model=TomadorOut, status_code=201)
def criar_tomador(body: TomadorIn, db: Session = Depends(get_db), _u: CurrentUser = Depends(require_financeiro)):
    dados = body.model_dump()
    dados["uf"] = dados["uf"].upper() if dados["uf"] else None
    return _gravar_tomador(db, TomadorDB(**dados, origem="manual"))


@router.patch("/tomadores/{tomador_id}", response_model=TomadorOut)
def alterar_tomador(tomador_id: int, body: TomadorPatch, db: Session = Depends(get_db),
                    _u: CurrentUser = Depends(require_financeiro)):
    t = db.get(TomadorDB, tomador_id)
    if t is None:
        raise HTTPException(404, "Tomador nao encontrado")
    for campo, valor in body.model_dump(exclude_unset=True).items():
        if valor is None and campo in ("nome", "emails", "optante_simples", "orgao_publico", "ativo"):
            raise HTTPException(400, f"{campo} nao pode ser vazio")
        setattr(t, campo, valor.upper() if campo == "uf" and valor else valor)
    db.commit()
    return t


def _contratantes(db: Session, contract_id: str) -> list[dict]:
    versao = (
        db.query(ContractVersionDB.form_data_json)
        .join(ContractDB, (ContractDB.contract_id == ContractVersionDB.contract_id)
              & (ContractDB.current_version == ContractVersionDB.version_number))
        .filter(ContractDB.contract_id == contract_id)
        .first()
    )
    if versao is None:
        raise HTTPException(404, "Contrato nao encontrado")
    try:
        lista = json.loads(versao[0]).get("contratantes") or []
    except (ValueError, AttributeError):
        lista = []
    return [c for c in lista if isinstance(c, dict)]


@router.post("/tomadores/de-contrato/{contract_id}", response_model=TomadorOut)
def tomador_de_contrato(contract_id: str, documento: str | None = Query(default=None),
                        db: Session = Depends(get_db), _u: CurrentUser = Depends(require_financeiro)):
    """Perfil fiscal a partir do contratante do contrato (o 1o, ou o do `documento`). Se o tomador
    ja existe, devolve o existente sem mexer. O contrato guarda o endereco so como texto: so o CEP
    e aproveitado; o resto o financeiro completa."""
    contratantes = _contratantes(db, contract_id)
    alvo = normalizar_doc(documento)
    for c in contratantes:
        doc = normalizar_doc(c.get("cnpj") or c.get("cpf"))
        if doc and (not alvo or alvo == doc):
            break
    else:
        raise HTTPException(404, "Contratante nao encontrado no contrato")
    if len(doc) not in (11, 14):
        raise HTTPException(400, "Contratante sem CPF/CNPJ valido")
    existente = db.query(TomadorDB).filter(TomadorDB.documento == doc).first()
    if existente:
        return existente
    cep = re.search(r"\b(\d{5})-?(\d{3})\b", c.get("endereco") or "")
    emails = [e.strip() for e in (c.get("email"),) if e and e.strip()]
    return _gravar_tomador(db, TomadorDB(
        documento=doc, nome=(c.get("razao_social") or c.get("nome") or "").strip() or doc,
        emails=emails, cep="".join(cep.groups()) if cep else None, origem="contrato"))


# --- quem fatura o contrato -----------------------------------------------------

class FaturamentoIn(BaseModel):
    origem: str = Field(pattern=r"^(legalone|honorario)$")
    tomador_id: int | None = None
    servico_id: int | None = None
    gera_rascunho_mensal: bool = False


class FaturamentoOut(FaturamentoIn):
    contract_id: str


@router.get("/contratos/{contract_id}/faturamento", response_model=FaturamentoOut)
def obter_faturamento(contract_id: str, db: Session = Depends(get_db), _u: CurrentUser = Depends(require_financeiro)):
    cf = db.get(ContratoFaturamentoDB, contract_id)
    if cf is None:
        if db.query(ContractDB.id).filter(ContractDB.contract_id == contract_id).first() is None:
            raise HTTPException(404, "Contrato nao encontrado")
        return FaturamentoOut(contract_id=contract_id, origem="legalone")  # padrao: continua no Legal One
    return FaturamentoOut(contract_id=contract_id, origem=cf.origem, tomador_id=cf.tomador_id,
                          servico_id=cf.servico_id, gera_rascunho_mensal=bool(cf.gera_rascunho_mensal))


@router.put("/contratos/{contract_id}/faturamento", response_model=FaturamentoOut)
def definir_faturamento(contract_id: str, body: FaturamentoIn, db: Session = Depends(get_db),
                        _u: CurrentUser = Depends(require_financeiro)):
    if db.query(ContractDB.id).filter(ContractDB.contract_id == contract_id).first() is None:
        raise HTTPException(404, "Contrato nao encontrado")
    if body.tomador_id is not None and db.get(TomadorDB, body.tomador_id) is None:
        raise HTTPException(400, "Tomador inexistente")
    if body.servico_id is not None and db.get(ServicoDB, body.servico_id) is None:
        raise HTTPException(400, "Servico inexistente")
    if body.origem == "honorario" and not (body.tomador_id and body.servico_id):
        raise HTTPException(400, "Para faturar pelo Honorario, informe o tomador e o servico padrao")
    cf = db.get(ContratoFaturamentoDB, contract_id) or ContratoFaturamentoDB(contract_id=contract_id)
    cf.origem, cf.tomador_id, cf.servico_id = body.origem, body.tomador_id, body.servico_id
    cf.gera_rascunho_mensal = body.gera_rascunho_mensal
    db.add(cf)
    db.commit()
    return FaturamentoOut(contract_id=contract_id, **body.model_dump())


# --- faturas --------------------------------------------------------------------

STATUS_FATURA = ("rascunho", "aprovada", "emitindo", "emitida", "cancelada")


class FaturaIn(BaseModel):
    contract_id: str
    tomador_id: int
    servico_id: int
    competencia: date
    descricao: str | None = Field(default=None, min_length=1)
    valor_bruto: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    vencimento: date | None = None
    parcela_num: int = Field(default=1, ge=1)
    parcela_total: int = Field(default=1, ge=1)


class FaturaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tomador_id: int | None = None
    servico_id: int | None = None
    descricao: str | None = Field(default=None, min_length=1)
    valor_bruto: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=12)
    vencimento: date | None = None


class FaturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    contract_id: str
    tomador_id: int
    servico_id: int
    competencia: date
    descricao: str
    valor_bruto: Decimal
    vencimento: date | None
    parcela_num: int
    parcela_total: int
    origem: str
    status: str
    criada_por: str
    aprovada_por: str | None


class TotalStatus(BaseModel):
    quantidade: int
    valor: Decimal


class FaturasOut(BaseModel):
    itens: list[FaturaOut]
    totais: dict[str, TotalStatus]  # faixa de totais por status (sobre o filtro de contrato/competencia)


@router.get("/faturas", response_model=FaturasOut)
def listar_faturas(
    status: str | None = Query(default=None), contract_id: str | None = None,
    competencia: date | None = None, db: Session = Depends(get_db), _u: CurrentUser = Depends(require_financeiro),
):
    if status and status not in STATUS_FATURA:
        raise HTTPException(400, "Status invalido")
    base = db.query(FaturaDB)
    if contract_id:
        base = base.filter(FaturaDB.contract_id == contract_id)
    if competencia:
        base = base.filter(FaturaDB.competencia == competencia.replace(day=1))
    totais = {s: TotalStatus(quantidade=0, valor=Decimal("0")) for s in STATUS_FATURA}
    for st, qtd, soma in base.with_entities(FaturaDB.status, func.count(), func.sum(FaturaDB.valor_bruto)).group_by(FaturaDB.status):
        totais[st] = TotalStatus(quantidade=qtd, valor=Decimal(soma or 0))
    lista = base.filter(FaturaDB.status == status) if status else base
    return FaturasOut(itens=lista.order_by(FaturaDB.competencia.desc(), FaturaDB.id.desc()).limit(500).all(), totais=totais)


@router.post("/faturas", response_model=FaturaOut, status_code=201)
def criar_fatura(body: FaturaIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require_financeiro)):
    if db.query(ContractDB.id).filter(ContractDB.contract_id == body.contract_id).first() is None:
        raise HTTPException(404, "Contrato nao encontrado")
    if db.get(TomadorDB, body.tomador_id) is None:
        raise HTTPException(400, "Tomador inexistente")
    servico = db.get(ServicoDB, body.servico_id)
    if servico is None:
        raise HTTPException(400, "Servico inexistente")
    if body.parcela_num > body.parcela_total:
        raise HTTPException(400, "parcela_num maior que parcela_total")
    f = FaturaDB(
        contract_id=body.contract_id, tomador_id=body.tomador_id, servico_id=body.servico_id,
        competencia=body.competencia.replace(day=1), descricao=body.descricao or servico.descricao_padrao,
        valor_bruto=body.valor_bruto, vencimento=body.vencimento, parcela_num=body.parcela_num,
        parcela_total=body.parcela_total, origem="manual", status="rascunho", criada_por=user.email,
    )
    db.add(f)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ja existe fatura desse contrato para essa competencia e parcela") from None
    return f


def _rascunho(db: Session, fatura_id: int) -> FaturaDB:
    f = db.get(FaturaDB, fatura_id)
    if f is None:
        raise HTTPException(404, "Fatura nao encontrada")
    return f


@router.patch("/faturas/{fatura_id}", response_model=FaturaOut)
def alterar_fatura(fatura_id: int, body: FaturaPatch, db: Session = Depends(get_db),
                   _u: CurrentUser = Depends(require_financeiro)):
    f = _rascunho(db, fatura_id)
    if f.status != "rascunho":
        raise HTTPException(409, "So fatura em rascunho pode ser editada")
    mudancas = body.model_dump(exclude_unset=True)
    if "tomador_id" in mudancas and db.get(TomadorDB, mudancas["tomador_id"]) is None:
        raise HTTPException(400, "Tomador inexistente")
    if "servico_id" in mudancas and db.get(ServicoDB, mudancas["servico_id"]) is None:
        raise HTTPException(400, "Servico inexistente")
    for campo, valor in mudancas.items():
        if valor is None and campo != "vencimento":
            raise HTTPException(400, f"{campo} nao pode ser vazio")
        setattr(f, campo, valor)
    db.commit()
    return f


@router.delete("/faturas/{fatura_id}", status_code=204)
def excluir_fatura(fatura_id: int, db: Session = Depends(get_db), _u: CurrentUser = Depends(require_financeiro)):
    f = _rascunho(db, fatura_id)
    if f.status != "rascunho":
        raise HTTPException(409, "So fatura em rascunho pode ser excluida")
    db.delete(f)
    db.commit()


@router.post("/faturas/{fatura_id}/aprovar", response_model=FaturaOut)
def aprovar_fatura(fatura_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_financeiro)):
    f = _rascunho(db, fatura_id)
    if f.status != "rascunho":
        raise HTTPException(409, f"Fatura {f.status}: so rascunho pode ser aprovado")
    f.status, f.aprovada_por = "aprovada", user.email
    db.commit()
    return f
