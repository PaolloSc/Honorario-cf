"""Schemas Pydantic para NFS-e."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class NFSeData(BaseModel):
    """Representacao canonica de uma NFS-e apos parse XML."""

    cnpj_prestador: str = Field(..., min_length=14, max_length=14)
    numero: str
    serie: Optional[str] = None
    codigo_verificacao: Optional[str] = None
    competencia: date
    data_emissao: date
    tomador_doc: str
    tomador_nome: Optional[str] = None
    valor_servicos: Decimal
    iss_retido: Decimal = Decimal("0")
    irrf: Decimal = Decimal("0")
    pis: Decimal = Decimal("0")
    cofins: Decimal = Decimal("0")
    csll: Decimal = Decimal("0")
    discriminacao: Optional[str] = None
    cancelada: bool = False
    data_cancelamento: Optional[datetime] = None
    xml_raw: bytes

    @computed_field
    @property
    def valor_liquido(self) -> Decimal:
        return (
            self.valor_servicos
            - self.iss_retido
            - self.irrf
            - self.pis
            - self.cofins
            - self.csll
        )


class CredencialPbhCreate(BaseModel):
    cnpj_prestador: str = Field(..., min_length=14, max_length=14)
    login: str
    senha: str


class CredencialPbhOut(BaseModel):
    id: int
    cnpj_prestador: str
    ativo: bool
    criado_em: datetime
    criado_por: str
    motivo_inativacao: Optional[str] = None


class NFSeOut(BaseModel):
    id: int
    cnpj_prestador: str
    numero: str
    serie: Optional[str]
    competencia: date
    data_emissao: date
    tomador_doc: str
    tomador_nome: Optional[str]
    valor_servicos: Decimal
    valor_liquido: Decimal
    cancelada: bool
    status_matching: str
    contract_id: Optional[str]
    participacao_id: Optional[int]
    pagamento_id: Optional[int]
    motivo: Optional[str]

    model_config = {"from_attributes": True}


class VincularRequest(BaseModel):
    contract_id: str
    motivo: Optional[str] = None


class IngestRequest(BaseModel):
    cnpj_prestador: str
    periodo_inicio: date
    periodo_fim: date
    origem: str = "cron"
    disparado_por: Optional[str] = None
    xmls_b64: list[str]


class SyncJobOut(BaseModel):
    id: int
    cnpj_prestador: str
    origem: str
    iniciado_em: datetime
    finalizado_em: Optional[datetime]
    periodo_inicio: date
    periodo_fim: date
    total_nfs: int
    auto_vinculadas: int
    pendentes: int
    sem_match: int
    erros: int
    status: str
    motivo_falha: Optional[str]

    model_config = {"from_attributes": True}
