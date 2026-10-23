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
    """Legado: aditivos salvos antes de 22/10/2026. Lido e ignorado."""

    valor_mensal: Optional[float] = None
    franquia_horas: Optional[int] = None
    valor_hora_excedente: Optional[float] = None


TIPO_ALTERAR, TIPO_EXCLUIR, TIPO_ADICIONAR = "alterar", "excluir", "adicionar"


class AlteracaoClausula(BaseModel):
    """Uma mudanca no contrato original: alterar, excluir ou adicionar clausula."""

    tipo: Literal["alterar", "excluir", "adicionar"]
    clausula: Optional[str] = None  # clausula do contrato original (alterar e excluir)
    texto: Optional[str] = None  # novo texto (alterar e adicionar)

    @model_validator(mode="after")
    def _campos_do_tipo(self):
        self.clausula = (self.clausula or "").strip() or None
        self.texto = (self.texto or "").strip() or None
        if self.tipo in (TIPO_ALTERAR, TIPO_EXCLUIR) and not self.clausula:
            raise ValueError("Informe a cláusula do contrato original")
        if self.tipo in (TIPO_ALTERAR, TIPO_ADICIONAR) and not self.texto:
            raise ValueError("Informe o novo texto")
        return self


class AditivoRequest(_ComOrigem):
    tipo_contrato: Literal["aditivo"] = TIPO_ADITIVO
    objeto: str = Field(min_length=1)
    alteracoes: list[AlteracaoClausula] = Field(default_factory=list)
    # Legado (aditivos salvos com remuneracao/abrangencia): aceitos e ignorados na geracao.
    remuneracao: Optional[Remuneracao] = None
    compensacao_anual: bool = False
    abrangencia: list[Empresa] = Field(default_factory=list)
    # Quando o contrato original foi firmado (nao a data de cadastro na plataforma). Obrigatoria:
    # o contrato de honorarios nao guarda essa data, entao o advogado informa.
    data_contrato_origem: str = Field(min_length=1)
    numero: int = 1  # servidor: 1 + aditivos ja existentes

    @model_validator(mode="after")
    def _ao_menos_uma_alteracao(self):
        # Aditivo legado (com remuneracao) continua gerando sem lista de alteracoes.
        if not self.alteracoes and self.remuneracao is None:
            raise ValueError("Informe ao menos uma alteração")
        return self


class DistratoRequest(_ComOrigem):
    tipo_contrato: Literal["distrato"] = TIPO_DISTRATO
    data_contrato_origem: str = Field(min_length=1)
    objeto_contrato_origem: str = Field(min_length=1)
    # Com ressalva dos honorarios e reembolsos vincendos, inclusive de exito (True, padrao) ou quitacao total (False).
    ressalva_exito: bool = True
    # Inclui a clausula de substabelecer sem reserva e devolver documentos.
    substabelecer_e_devolver: bool = False
    # Dados do substabelecimento gerado junto (so com substabelecer_e_devolver). Distratos salvos
    # antes dessa opcao nao o tem e nao geram nada novo.
    substabelecimento: Optional["SubstabelecimentoDoDistrato"] = None


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
    # genero/nacionalidade/estado_civil: legado (documentos salvos antes de 22/10/2026).
    # Sem genero, o texto sai neutro ("advogado(a)", "inscrito(a)").
    genero: Optional[Literal["F", "M"]] = None
    nacionalidade: str = ""  # vazio => brasileiro(a) conforme o genero
    estado_civil: str = ""
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
    endereco_substabelecidos: str = ""  # opcional: sem endereco, a frase some do texto
    processos: list[Processo] = Field(min_length=1)


class SubstabelecimentoDoDistrato(BaseModel):
    """O que o distrato precisa saber para gerar o substabelecimento: o cliente (outorgante) e a
    data vem do proprio contrato/distrato; aqui ficam quem recebe os poderes e os processos."""

    substabelecentes: list[Substabelecente] = Field(min_length=1)
    substabelecidos: list[Substabelecido] = Field(min_length=1)
    endereco_substabelecidos: str = ""
    processos: list[Processo] = Field(min_length=1)


DistratoRequest.model_rebuild()

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
