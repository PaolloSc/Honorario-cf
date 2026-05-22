"""Schemas Pydantic para TaxCode (alíquotas fiscais agregadas)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TaxCodeBase(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=32)
    descricao: str = Field(..., min_length=1, max_length=256)
    aliquota_total: float = Field(..., ge=0, le=1)
    aliquota_iss: float = Field(0, ge=0, le=1)
    aliquota_pis: float = Field(0, ge=0, le=1)
    aliquota_cofins: float = Field(0, ge=0, le=1)
    aliquota_irrf: float = Field(0, ge=0, le=1)
    aliquota_csll: float = Field(0, ge=0, le=1)

    @field_validator("codigo")
    @classmethod
    def upper_codigo(cls, v: str) -> str:
        return v.strip().upper()


class TaxCodeCreate(TaxCodeBase):
    pass


class TaxCodeUpdate(BaseModel):
    descricao: Optional[str] = None
    aliquota_total: Optional[float] = None
    aliquota_iss: Optional[float] = None
    aliquota_pis: Optional[float] = None
    aliquota_cofins: Optional[float] = None
    aliquota_irrf: Optional[float] = None
    aliquota_csll: Optional[float] = None


class TaxCodeOut(TaxCodeBase):
    id: int
    ativo: bool
    criado_em: datetime
    criado_por: str

    model_config = {"from_attributes": True}
