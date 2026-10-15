"""Configuracao do emissor de NFS-e: prestador, parametros fiscais e certificado A1.

So papel financeiro (ou admin). O .pfx e a senha entram cifrados e nunca saem: nem na
resposta, nem em log, nem na trilha de auditoria. O ambiente fica em 'homologacao'
(producao restrita) a menos que settings.nfse_emissao_producao_permitida seja ligada."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone

from cryptography.x509.oid import NameOID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_financeiro
from app.config import settings
from app.database import get_db
from app.models.emissao_db import EmissorConfigDB
from app.services.emissor_cert import guardar_certificado, tem_certificado
from workers.nfse_adn.cert import CertificadoError, carregar_pfx

router = APIRouter(prefix="/api/emissor", tags=["emissor"])

MAX_PFX_BYTES = 200_000


def _cnpj_valido(c: str) -> bool:
    if len(c) != 14 or not c.isdigit() or len(set(c)) == 1:
        return False
    for n in (12, 13):
        pesos = list(range(n - 7, 1, -1)) + list(range(9, 1, -1))
        resto = sum(int(d) * p for d, p in zip(c[:n], pesos)) % 11
        if int(c[n]) != (0 if resto < 2 else 11 - resto):
            return False
    return True


class EmissorIn(BaseModel):
    cnpj: str
    razao_social: str = Field(min_length=1, max_length=256)
    inscricao_municipal: str | None = Field(default=None, max_length=15)
    municipio_ibge: str = Field(default="3106200", pattern=r"^\d{7}$")
    op_simp_nac: str = Field(default="1", pattern=r"^[123]$")
    reg_ap_trib_sn: str | None = Field(default=None, pattern=r"^[123]$")
    reg_esp_trib: str = Field(default="0", pattern=r"^[0-69]$")
    serie_dps: str = Field(default="900", pattern=r"^\d{1,5}$")
    ambiente: str = Field(default="homologacao", pattern=r"^(homologacao|producao)$")
    ativo: bool = False


class EmissorOut(BaseModel):
    configurado: bool
    cnpj: str | None = None
    razao_social: str | None = None
    inscricao_municipal: str | None = None
    municipio_ibge: str | None = None
    op_simp_nac: str | None = None
    reg_ap_trib_sn: str | None = None
    reg_esp_trib: str | None = None
    serie_dps: str | None = None
    ambiente: str | None = None
    ativo: bool = False
    tem_certificado: bool = False
    cert_titular: str | None = None
    cert_validade: date | None = None
    producao_permitida: bool = False


def _out(cfg: EmissorConfigDB | None) -> EmissorOut:
    if cfg is None:
        return EmissorOut(configurado=False, producao_permitida=settings.nfse_emissao_producao_permitida)
    return EmissorOut(
        configurado=True, cnpj=cfg.cnpj, razao_social=cfg.razao_social, inscricao_municipal=cfg.inscricao_municipal,
        municipio_ibge=cfg.municipio_ibge, op_simp_nac=cfg.op_simp_nac, reg_ap_trib_sn=cfg.reg_ap_trib_sn,
        reg_esp_trib=cfg.reg_esp_trib, serie_dps=cfg.serie_dps, ambiente=cfg.ambiente, ativo=bool(cfg.ativo),
        tem_certificado=tem_certificado(cfg), cert_titular=cfg.cert_titular, cert_validade=cfg.cert_validade,
        producao_permitida=settings.nfse_emissao_producao_permitida,
    )


def _auditar(db: Session, acao: str, user: CurrentUser, payload: dict) -> None:
    db.execute(
        text("INSERT INTO nfse_audit_log (acao, user_email, payload_after, ts) VALUES (:a, :u, :p, :t)"),
        {"a": acao, "u": user.email, "p": json.dumps(payload), "t": datetime.now(timezone.utc)},
    )


@router.get("", response_model=EmissorOut)
def obter(db: Session = Depends(get_db), user: CurrentUser = Depends(require_financeiro)):
    return _out(db.get(EmissorConfigDB, 1))


@router.put("", response_model=EmissorOut)
def salvar(body: EmissorIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require_financeiro)):
    cnpj = re.sub(r"\D", "", body.cnpj)
    if not _cnpj_valido(cnpj):
        raise HTTPException(400, "CNPJ invalido")
    if body.ambiente == "producao" and not settings.nfse_emissao_producao_permitida:
        raise HTTPException(400, "Emissao em producao nao esta habilitada: use o ambiente 'homologacao'")
    if body.reg_ap_trib_sn and body.op_simp_nac != "3":
        raise HTTPException(400, "Regime de apuracao do SN so existe para ME/EPP (op_simp_nac=3)")

    cfg = db.get(EmissorConfigDB, 1)
    if cfg is None:
        cfg = EmissorConfigDB(id=1, cnpj=cnpj, razao_social=body.razao_social)
        db.add(cfg)
    elif cfg.cnpj != cnpj and tem_certificado(cfg):
        raise HTTPException(409, "O certificado atual e do CNPJ anterior: envie de novo o certificado do novo CNPJ")
    if body.ativo and not tem_certificado(cfg):
        raise HTTPException(400, "Envie o certificado antes de ativar o emissor")

    cfg.cnpj, cfg.razao_social = cnpj, body.razao_social
    cfg.inscricao_municipal = body.inscricao_municipal or None
    cfg.municipio_ibge, cfg.op_simp_nac = body.municipio_ibge, body.op_simp_nac
    cfg.reg_ap_trib_sn, cfg.reg_esp_trib = body.reg_ap_trib_sn, body.reg_esp_trib
    cfg.serie_dps, cfg.ambiente, cfg.ativo = body.serie_dps, body.ambiente, body.ativo
    cfg.atualizado_por = user.email
    _auditar(db, "emissor.config", user, {"cnpj": cnpj, "ambiente": body.ambiente, "ativo": body.ativo})
    db.commit()
    db.refresh(cfg)
    return _out(cfg)


@router.post("/certificado", response_model=EmissorOut)
async def enviar_certificado(
    pfx: UploadFile = File(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_financeiro),
):
    if not settings.nfse_kek:
        raise HTTPException(503, "NFSE_KEK nao configurada no servidor")
    cfg = db.get(EmissorConfigDB, 1)
    if cfg is None:
        raise HTTPException(409, "Salve os dados do emissor (CNPJ) antes de enviar o certificado")
    conteudo = await pfx.read(MAX_PFX_BYTES + 1)
    if not conteudo or len(conteudo) > MAX_PFX_BYTES:
        raise HTTPException(400, "Arquivo .pfx vazio ou grande demais")
    try:
        _, cert, _ = carregar_pfx(conteudo, senha)
    except CertificadoError:
        raise HTTPException(400, "Certificado .pfx invalido ou senha incorreta") from None
    validade = cert.not_valid_after_utc.date()
    if validade < date.today():
        raise HTTPException(400, f"Certificado vencido em {validade:%d/%m/%Y}")
    if cfg.cnpj not in cert.subject.rfc4514_string():
        raise HTTPException(400, "O certificado nao e do CNPJ do emissor")
    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    guardar_certificado(cfg, conteudo, senha)
    cfg.cert_titular = (cn[0].value if cn else "")[:256] or None
    cfg.cert_validade = validade
    cfg.ativo = False  # certificado novo: reativar de proposito depois de testar
    cfg.atualizado_por = user.email
    _auditar(db, "emissor.certificado", user, {"cnpj": cfg.cnpj, "validade": validade.isoformat()})
    db.commit()
    db.refresh(cfg)
    return _out(cfg)
