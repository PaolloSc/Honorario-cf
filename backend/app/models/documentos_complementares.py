"""Documentos complementares de um contrato: aditivo, distrato e substabelecimento.

O texto dos modelos e' fixo (os advogados nao reescrevem clausulas); o que varia
sao as partes, o objeto, a remuneracao, os processos etc. Campos marcados como
"servidor" sao preenchidos pelo backend a partir do contrato de origem — o que o
cliente enviar neles e' descartado — e ficam gravados no form_data para a
regeneracao do .docx (edicao, DocuSeal) nao depender de consulta ao banco.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

TIPO_ADITIVO = "aditivo"
TIPO_DISTRATO = "distrato"
TIPO_SUBSTABELECIMENTO = "substabelecimento"
TIPOS_COMPLEMENTARES = (TIPO_ADITIVO, TIPO_DISTRATO, TIPO_SUBSTABELECIMENTO)

ROTULO_DOCUMENTO = {
    TIPO_ADITIVO: "Aditivo Contratual",
    TIPO_DISTRATO: "Distrato",
    TIPO_SUBSTABELECIMENTO: "Substabelecimento",
}

# Numero unico do CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO (DD = digito verificador, mod 97)
_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_CNJ = re.compile(r"^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$")


def _cnj_valido(numero: str) -> bool:
    m = _CNJ.match(numero)
    if not m:
        return False
    seq, dv, ano, j, tr, origem = m.groups()
    return 98 - (int(seq + ano + j + tr + origem + "00") % 97) == int(dv)


class AditivoAnterior(BaseModel):
    """Aditivo ja cadastrado no contrato de origem (servidor)."""

    numero: int
    data_documento: Optional[str] = None
    objeto: str = ""


class _DocumentoComplementar(BaseModel):
    contrato_origem_id: Optional[str] = None
    data_documento: Optional[str] = None  # ISO yyyy-mm-dd; vazio = hoje
    email_destinatario: Optional[str] = None

    @field_validator("data_documento", "data_contrato_origem", check_fields=False)
    @classmethod
    def _data_iso(cls, v):
        if v in (None, ""):
            return None
        if not isinstance(v, str) or not _DATA_ISO.fullmatch(v):
            raise ValueError("Data inválida (use AAAA-MM-DD)")
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("Data inválida (use AAAA-MM-DD)")
        return v


class _ComOrigem(_DocumentoComplementar):
    contrato_origem_id: str = Field(min_length=1)
    contratantes: list[dict] = Field(default_factory=list)  # servidor: copia do contrato de origem
    aditivos_anteriores: list[AditivoAnterior] = Field(default_factory=list)  # servidor


class Empresa(BaseModel):
    razao_social: str = Field(min_length=1)
    cnpj: str = Field(min_length=1)


class Remuneracao(BaseModel):
    valor_mensal: float = Field(gt=0)
    # Opcionais: sem franquia / hora excedente as clausulas correspondentes somem.
    franquia_horas: Optional[int] = Field(default=None, gt=0)
    valor_hora_excedente: Optional[float] = Field(default=None, gt=0)


class AditivoRequest(_ComOrigem):
    tipo_contrato: Literal["aditivo"] = TIPO_ADITIVO
    objeto: str = Field(min_length=1)
    remuneracao: Remuneracao
    compensacao_anual: bool = True
    abrangencia: list[Empresa] = Field(default_factory=list)
    # Quando o contrato original foi firmado (nao a data de cadastro na plataforma). Obrigatoria:
    # o contrato de honorarios nao guarda essa data, entao o advogado informa.
    data_contrato_origem: str = Field(min_length=1)
    numero: int = 1  # servidor: 1 + aditivos ja existentes


class DistratoRequest(_ComOrigem):
    tipo_contrato: Literal["distrato"] = TIPO_DISTRATO
    data_contrato_origem: str = Field(min_length=1)
    objeto_contrato_origem: str = Field(min_length=1)
    # Com ressalva dos honorarios e reembolsos vincendos, inclusive de exito (True, padrao) ou quitacao total (False).
    ressalva_exito: bool = True
    # Inclui a clausula de substabelecer sem reserva e devolver documentos.
    substabelecer_e_devolver: bool = False


class Outorgante(BaseModel):
    """Cliente que outorgou os poderes: empresa (razao_social) ou pessoa fisica (nome)."""

    razao_social: Optional[str] = None
    nome: Optional[str] = None
    cnpj: Optional[str] = None
    cpf: Optional[str] = None

    @model_validator(mode="after")
    def _tem_nome(self):
        if not (self.razao_social or self.nome):
            raise ValueError("Informe a razão social ou o nome do outorgante")
        return self

    @property
    def exibicao(self) -> str:
        return self.razao_social or self.nome or ""


class Substabelecente(BaseModel):
    """Advogado do escritorio que substabelece. A OAB vai aqui: o cadastro nao a tem."""

    nome: str = Field(min_length=1)
    oab: str = Field(min_length=1)  # ja redigida: "OAB/MG n.º 36.959"
    email: str = Field(min_length=1)


class Substabelecido(BaseModel):
    nome: str = Field(min_length=1)
    genero: Literal["F", "M"] = "M"
    nacionalidade: str = ""  # vazio => brasileiro(a) conforme o genero
    estado_civil: str = Field(min_length=1)
    oab: str = Field(min_length=1)  # ja redigida: "OAB/MG sob o n.º 101.728"


class Processo(BaseModel):
    numero: str
    descricao: str = ""  # "Parte A x Parte B"
    tipo: str = "Processo"  # livre: "Processo", "Agravo de Instrumento"...

    @field_validator("numero")
    @classmethod
    def _numero_cnj(cls, v: str) -> str:
        v = v.strip()
        if not _cnj_valido(v):
            raise ValueError("Número de processo inválido (padrão CNJ 0000000-00.0000.0.00.0000, com dígito verificador)")
        return v


class SubstabelecimentoRequest(_DocumentoComplementar):
    tipo_contrato: Literal["substabelecimento"] = TIPO_SUBSTABELECIMENTO
    outorgante: Outorgante
    substabelecentes: list[Substabelecente] = Field(min_length=1)
    substabelecidos: list[Substabelecido] = Field(min_length=1)
    endereco_substabelecidos: str = Field(min_length=1)
    processos: list[Processo] = Field(min_length=1)


REQUESTS = {
    TIPO_ADITIVO: AditivoRequest,
    TIPO_DISTRATO: DistratoRequest,
    TIPO_SUBSTABELECIMENTO: SubstabelecimentoRequest,
}


def nome_exibicao(data) -> str:
    """Nome do cliente para a lista de contratos."""
    if isinstance(data, SubstabelecimentoRequest):
        return data.outorgante.exibicao
    return nome_contratante(data.contratantes[0]) if data.contratantes else ""


def nome_contratante(c: dict) -> str:
    return c.get("razao_social") or c.get("nome") or ""


def email_contato(data) -> str:
    if isinstance(data, SubstabelecimentoRequest) or not data.contratantes:
        return ""
    c = data.contratantes[0]
    if c.get("email"):
        return c["email"]
    reps = c.get("representantes") or []
    return next((r.get("email") for r in reps if r.get("email")), "") or c.get("representante_email") or ""
