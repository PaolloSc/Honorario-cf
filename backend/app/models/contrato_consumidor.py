"""Contrato de prestacao de servicos advocaticios — consumidor / transporte aereo.

Modelo separado do contrato de honorarios: o texto e' fixo (25% de exito, Monica
como contratada, dados bancarios e tabela do milheiro), e o que varia sao as
partes, a companhia re' e alguns parametros do caso.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

TIPO_CONSUMIDOR_AEREO = "consumidor_aereo"

# Valor do milheiro (1.000 milhas) por companhia — tabela fixa do escritorio.
# So' a linha da companhia do caso e' impressa no contrato.
MILHEIRO_POR_COMPANHIA: dict[str, float] = {
    "Gol": 40.0,
    "Latam": 40.0,
    "Azul": 40.0,
    "Aeroméxico": 60.0,
    "Avianca": 60.0,
    "American Airlines": 80.0,
    "United Airlines": 80.0,
    "Delta Air Lines": 80.0,
    "Air Canada": 80.0,
    "Iberia L.A.E": 80.0,
    "Air France": 80.0,
    "Lufthansa": 80.0,
    "British Airways": 80.0,
    "TAP": 80.0,
    "KLM": 80.0,
    "Emirates": 100.0,
    "Qatar Airways": 100.0,
    "Japan Airlines": 100.0,
}


class ContratanteConsumidorPF(BaseModel):
    """Qualificacao do consumidor. Sem profissao/estado civil — o modelo nao usa."""

    tipo: Literal["PF"] = "PF"
    nome: str
    genero: Literal["F", "M"] = "F"  # concordancia: inscrita/inscrito, domiciliada/domiciliado
    nacionalidade: str = ""  # vazio => "brasileira"/"brasileiro" conforme genero
    cpf: str
    rg: Optional[str] = None
    endereco: str
    email: Optional[str] = None
    celular: Optional[str] = None


class ContratanteConsumidorPJ(BaseModel):
    """Empresa contratante, qualificada com o representante legal que assina."""

    tipo: Literal["PJ"] = "PJ"
    razao_social: str
    cnpj: str
    endereco: str
    email: Optional[str] = None
    representante_nome: str
    representante_cpf: str
    representante_genero: Literal["F", "M"] = "F"
    representante_nacionalidade: str = ""
    representante_email: Optional[str] = None


ContratanteConsumidor = Annotated[
    Union[ContratanteConsumidorPF, ContratanteConsumidorPJ],
    Field(discriminator="tipo"),
]


def nome_exibicao(c: ContratanteConsumidorPF | ContratanteConsumidorPJ) -> str:
    return c.razao_social if isinstance(c, ContratanteConsumidorPJ) else c.nome


def email_contato(c: ContratanteConsumidorPF | ContratanteConsumidorPJ) -> str:
    """Quem recebe o contrato e assina: na PJ, o representante legal."""
    if isinstance(c, ContratanteConsumidorPJ):
        return c.representante_email or c.email or ""
    return c.email or ""


def nome_signatario(c: ContratanteConsumidorPF | ContratanteConsumidorPJ) -> str:
    if isinstance(c, ContratanteConsumidorPJ):
        return c.representante_nome
    return c.nome


class ReAerea(BaseModel):
    """Companhia aerea Re'. Uma acao pode ter mais de uma no polo passivo."""

    companhia: str  # chave de MILHEIRO_POR_COMPANHIA (define o valor padrao do milheiro)
    razao_social: str  # como vai na clausula II: "KLM CIA REAL HOLANDESA DE AVIACAO"
    cnpj: str
    # Permite ajustar o milheiro caso a caso sem mexer na tabela.
    valor_milheiro_override: Optional[float] = None

    @property
    def valor_milheiro(self) -> float:
        if self.valor_milheiro_override is not None:
            return self.valor_milheiro_override
        return MILHEIRO_POR_COMPANHIA.get(self.companhia, 0.0)


class ContratoConsumidorRequest(BaseModel):
    tipo_contrato: Literal["consumidor_aereo"] = TIPO_CONSUMIDOR_AEREO
    contratantes: list[ContratanteConsumidor] = Field(min_length=1)
    res: list[ReAerea] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _compatibilidade(cls, data):
        if not isinstance(data, dict):
            return data

        # Contratante sem 'tipo' e' pessoa fisica — o campo so' existe desde a PJ.
        for c in data.get("contratantes") or []:
            if isinstance(c, dict) and not c.get("tipo"):
                c["tipo"] = "PF"

        # Contratos gravados antes das multiplas Res tinham uma companhia so',
        # em campos soltos. Dobra os campos antigos na lista nova.
        if not data.get("res") and data.get("companhia"):
            data["res"] = [
                {
                    "companhia": data.get("companhia"),
                    "razao_social": data.get("re_razao_social", ""),
                    "cnpj": data.get("re_cnpj", ""),
                    "valor_milheiro_override": data.get("valor_milheiro_override"),
                }
            ]
        return data

    juizado: str = "Juizado Especial Cível de Belo Horizonte - MG"
    prazo_pagamento_dias: int = 10
    # True: a CONTRATADA elabora a reclamacao para a plataforma (Reclame Aqui).
    # False: apenas orienta o CONTRATANTE a apresenta-la.
    elabora_reclamacao: bool = True
    data_contrato: Optional[str] = None  # ISO yyyy-mm-dd; vazio = data de hoje
    comarca: str = "Belo Horizonte"  # foro e cidade de assinatura

    email_destinatario: Optional[str] = None

    @property
    def plural(self) -> bool:
        return len(self.contratantes) > 1
