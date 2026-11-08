"""Como uma nota emitida (NFS-e) aparece para a tela: usado pelas rotas do emissor e do faturamento."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.emissao_db import NfseEmitidaDB


class NfseEmitidaOut(BaseModel):
    id: int
    fatura_id: int
    status: str
    ambiente: str
    dps_serie: str
    dps_numero: int
    chave_acesso: str | None
    numero_nfse: str | None
    valor_servicos: str
    iss: str
    erro_codigo: str | None
    erro_mensagem: str | None
    emitida_em: datetime | None
    emitida_por: str
    criado_em: datetime | None
    tem_xml: bool


def nota_out(n: NfseEmitidaDB) -> NfseEmitidaOut:
    return NfseEmitidaOut(
        id=n.id, fatura_id=n.fatura_id, status=n.status, ambiente=n.ambiente, dps_serie=n.dps_serie,
        dps_numero=n.dps_numero, chave_acesso=n.chave_acesso, numero_nfse=n.numero_nfse,
        valor_servicos=f"{n.valor_servicos:.2f}", iss=f"{n.iss:.2f}", erro_codigo=n.erro_codigo,
        erro_mensagem=n.erro_mensagem, emitida_em=n.emitida_em, emitida_por=n.emitida_por,
        criado_em=n.criado_em, tem_xml=bool(n.xml_nfse),
    )
