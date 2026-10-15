"""Emissao de NFS-e pelo Emissor Nacional: 8 tabelas (migracao 0014_emissao_nfse).

Estilo do projeto: PK Integer, dinheiro Numeric(12,2), datas de negocio Date, instantes
DateTime(timezone=True); nada exclusivo de Postgres alem dos indices parciais (que tem
variante SQLite). Os parametros fiscais aceitos pelo SEFIN (regime, IM, codigos de servico,
NBS, aliquota) sao CONFIGURACAO nas tabelas emissor_config e servicos, nao constantes."""
from __future__ import annotations

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer,
    LargeBinary, Numeric, String, Text, UniqueConstraint, func, text,
)

from app.database import Base
from app.models import nfse_db  # noqa: F401  (registra nfse_recebidas, alvo da FK nfse_emitidas.nfse_recebida_id)


class EmissorConfigDB(Base):
    """Prestador (linha unica) e certificado A1 cifrado com a KEK, no padrao de credencial_pbh."""
    __tablename__ = "emissor_config"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_emissor_linha_unica"),
        CheckConstraint("ambiente in ('homologacao','producao')", name="ck_emissor_ambiente"),
        CheckConstraint("op_simp_nac in ('1','2','3')", name="ck_emissor_op_simp_nac"),
    )
    id = Column(Integer, primary_key=True, default=1)
    cnpj = Column(String(14), nullable=False, unique=True)
    razao_social = Column(String(256), nullable=False)
    inscricao_municipal = Column(String(15), nullable=True)
    municipio_ibge = Column(String(7), nullable=False, default="3106200", server_default="3106200")  # BH
    op_simp_nac = Column(String(1), nullable=False, default="1", server_default="1")  # 1 nao optante, 2 MEI, 3 ME/EPP
    reg_ap_trib_sn = Column(String(1), nullable=True)       # so ME/EPP: 1 tudo pelo SN, 2/3 ISS fora
    reg_esp_trib = Column(String(1), nullable=False, default="0", server_default="0")
    serie_dps = Column(String(5), nullable=False, default="900", server_default="900")
    ambiente = Column(String(16), nullable=False, default="homologacao", server_default="homologacao")
    cert_pfx_enc = Column(LargeBinary, nullable=True)       # base64 do .pfx, cifrado (AES-GCM)
    cert_pfx_nonce = Column(LargeBinary, nullable=True)
    cert_senha_enc = Column(LargeBinary, nullable=True)
    cert_senha_nonce = Column(LargeBinary, nullable=True)
    cert_titular = Column(String(256), nullable=True)
    cert_validade = Column(Date, nullable=True)
    ativo = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    atualizado_em = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    atualizado_por = Column(String(255), nullable=True)


class DpsSequenceDB(Base):
    """Numeracao da DPS por prestador, serie e ambiente (incremento atomico: proximo_dps)."""
    __tablename__ = "dps_sequence"
    cnpj = Column(String(14), primary_key=True)
    serie = Column(String(5), primary_key=True)
    ambiente = Column(String(16), primary_key=True)
    ultimo_numero = Column(Integer, nullable=False, default=0, server_default="0")


class ServicoDB(Base):
    """Servico faturavel com os dados fiscais da DPS. IBS/CBS e opcional por servico."""
    __tablename__ = "servicos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False, unique=True)
    descricao_padrao = Column(Text, nullable=False, default="Referente a serviços advocatícios")
    codigo_lc116 = Column(String(10), nullable=True)
    c_trib_nac = Column(String(6), nullable=False)          # 6 digitos, ex.: 171401
    c_trib_mun = Column(String(3), nullable=True)           # municipal, ex.: 001 (BH parametriza em 17.14.01.001)
    nbs = Column(String(9), nullable=True)                  # 9 digitos, sem pontos
    aliquota_iss = Column(Numeric(5, 2), nullable=True)     # so quando a regra do regime exige pAliq
    iss_retido_padrao = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    incluir_ibscbs = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    c_ind_op = Column(String(6), nullable=True)             # IBS/CBS: indicador da operacao
    cst_ibscbs = Column(String(3), nullable=True)
    c_class_trib = Column(String(6), nullable=True)
    tax_code_id = Column(Integer, ForeignKey("tax_codes.id"), nullable=True, index=True)
    ativo = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    criado_por = Column(String(255), nullable=False)


class TomadorDB(Base):
    """Perfil fiscal do cliente. O contrato guarda so o texto do endereco, a nota precisa dele estruturado."""
    __tablename__ = "tomadores"
    id = Column(Integer, primary_key=True, autoincrement=True)
    documento = Column(String(14), nullable=False, unique=True)     # so digitos (CNPJ ou CPF)
    nome = Column(String(256), nullable=False)
    emails = Column(JSON, nullable=False, default=list)
    inscricao_municipal = Column(String(30), nullable=True)
    optante_simples = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    orgao_publico = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    cep = Column(String(8), nullable=True)
    logradouro = Column(String(256), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(120), nullable=True)
    bairro = Column(String(120), nullable=True)
    municipio_ibge = Column(String(7), nullable=True)
    uf = Column(String(2), nullable=True)
    origem = Column(String(20), nullable=False, default="manual", server_default="manual")  # cnpj|contrato|manual
    ativo = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class ContratoFaturamentoDB(Base):
    """Quem fatura o contrato e com quais padroes: trava contra nota em duplicidade na transicao do Legal One."""
    __tablename__ = "contrato_faturamento"
    __table_args__ = (CheckConstraint("origem in ('legalone','honorario')", name="ck_cf_origem"),)
    contract_id = Column(String(64), ForeignKey("contracts.contract_id"), primary_key=True)
    origem = Column(String(16), nullable=False, default="legalone", server_default="legalone")
    tomador_id = Column(Integer, ForeignKey("tomadores.id"), nullable=True)
    servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=True)
    gera_rascunho_mensal = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    atualizado_em = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class FaturaDB(Base):
    """Item faturavel: o que vira uma DPS."""
    __tablename__ = "faturas"
    __table_args__ = (
        UniqueConstraint("contract_id", "competencia", "origem", "parcela_num", name="uq_fatura_geracao"),
        CheckConstraint("status in ('rascunho','aprovada','emitindo','emitida','cancelada')", name="ck_fatura_status"),
        CheckConstraint("origem in ('manual','mensalidade','prolabore','exito','hora')", name="ck_fatura_origem"),
        CheckConstraint("valor_bruto > 0", name="ck_fatura_valor"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(64), ForeignKey("contracts.contract_id"), nullable=False, index=True)
    tomador_id = Column(Integer, ForeignKey("tomadores.id"), nullable=False, index=True)
    servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=False)
    competencia = Column(Date, nullable=False)               # 1o dia do mes
    descricao = Column(Text, nullable=False)
    valor_bruto = Column(Numeric(12, 2), nullable=False)
    vencimento = Column(Date, nullable=True)
    parcela_num = Column(Integer, nullable=False, default=1, server_default="1")
    parcela_total = Column(Integer, nullable=False, default=1, server_default="1")
    origem = Column(String(16), nullable=False, default="manual", server_default="manual")
    status = Column(String(16), nullable=False, default="rascunho", server_default="rascunho", index=True)
    criada_por = Column(String(255), nullable=False)
    aprovada_por = Column(String(255), nullable=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class NfseEmitidaDB(Base):
    __tablename__ = "nfse_emitidas"
    __table_args__ = (
        CheckConstraint("status in ('processando','autorizada','rejeitada','cancelada')", name="ck_nfse_emitida_status"),
        UniqueConstraint("cnpj_prestador", "ambiente", "dps_serie", "dps_numero", name="uq_nfse_emitida_dps"),
        # no maximo uma nota viva por fatura: a segunda emissao simultanea falha no banco
        Index("uq_nfse_emitida_viva", "fatura_id", unique=True,
              sqlite_where=text("status in ('processando','autorizada')"),
              postgresql_where=text("status in ('processando','autorizada')")),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    fatura_id = Column(Integer, ForeignKey("faturas.id"), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="processando", server_default="processando", index=True)
    ambiente = Column(String(16), nullable=False)
    cnpj_prestador = Column(String(14), nullable=False)
    dps_serie = Column(String(5), nullable=False)
    dps_numero = Column(Integer, nullable=False)
    idempotency_key = Column(String(80), nullable=False, unique=True)
    chave_acesso = Column(String(60), nullable=True)
    numero_nfse = Column(String(40), nullable=True)
    valor_servicos = Column(Numeric(12, 2), nullable=False)
    iss = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    retencoes = Column(JSON, nullable=False, default=dict)   # PIS, Cofins, CSLL, IRRF, INSS, ISS retido
    tomador_snapshot = Column(JSON, nullable=False)          # copia imutavel do cliente na emissao
    servico_snapshot = Column(JSON, nullable=False)          # copia do codigo de servico e das aliquotas
    xml_dps = Column(LargeBinary, nullable=True)
    xml_nfse = Column(LargeBinary, nullable=True)
    erro_codigo = Column(String(20), nullable=True)
    erro_mensagem = Column(Text, nullable=True)
    nfse_recebida_id = Column(Integer, ForeignKey("nfse_recebidas.id"), nullable=True)  # elo com matcher e participacao
    emitida_em = Column(DateTime(timezone=True), nullable=True)
    cancelada_em = Column(DateTime(timezone=True), nullable=True)
    motivo_cancelamento = Column(Text, nullable=True)
    emitida_por = Column(String(255), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class NfseEmitidaEventoDB(Base):
    __tablename__ = "nfse_emitida_eventos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nfse_emitida_id = Column(Integer, ForeignKey("nfse_emitidas.id"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False)               # enviada|resposta|consulta|erro|cancelamento
    payload = Column(JSON, nullable=False, default=dict)    # sem segredo, sem o PFX
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


PROXIMO_DPS_SQL = text(
    """
    INSERT INTO dps_sequence (cnpj, serie, ambiente, ultimo_numero) VALUES (:c, :s, :a, 1)
    ON CONFLICT (cnpj, serie, ambiente)
    DO UPDATE SET ultimo_numero = dps_sequence.ultimo_numero + 1
    RETURNING ultimo_numero
    """
)


def proximo_dps(db, cnpj: str, serie: str, ambiente: str) -> int:
    """Proximo numero da DPS. Atomico e igual em SQLite (>=3.35) e Postgres."""
    return db.execute(PROXIMO_DPS_SQL, {"c": cnpj, "s": serie, "a": ambiente}).scalar_one()
