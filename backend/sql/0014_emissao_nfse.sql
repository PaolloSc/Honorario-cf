-- Emissao de NFS-e (migracao 0014_emissao_nfse): 8 tabelas. IDEMPOTENTE: pode rodar duas vezes.
-- Gerado a partir de app/models/emissao_db.py. Rodar no Neon ANTES do merge da PR.
-- Pre-requisito: ja existem contracts, tax_codes e nfse_recebidas.

BEGIN;

CREATE TABLE IF NOT EXISTS emissor_config (
	id INTEGER NOT NULL, 
	cnpj VARCHAR(14) NOT NULL, 
	razao_social VARCHAR(256) NOT NULL, 
	inscricao_municipal VARCHAR(15), 
	municipio_ibge VARCHAR(7) DEFAULT '3106200' NOT NULL, 
	op_simp_nac VARCHAR(1) DEFAULT '1' NOT NULL, 
	reg_ap_trib_sn VARCHAR(1), 
	reg_esp_trib VARCHAR(1) DEFAULT '0' NOT NULL, 
	serie_dps VARCHAR(5) DEFAULT '900' NOT NULL, 
	ambiente VARCHAR(16) DEFAULT 'homologacao' NOT NULL, 
	cert_pfx_enc BYTEA, 
	cert_pfx_nonce BYTEA, 
	cert_senha_enc BYTEA, 
	cert_senha_nonce BYTEA, 
	cert_titular VARCHAR(256), 
	cert_validade DATE, 
	ativo BOOLEAN DEFAULT false NOT NULL, 
	atualizado_em TIMESTAMP WITH TIME ZONE, 
	atualizado_por VARCHAR(255), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_emissor_linha_unica CHECK (id = 1), 
	CONSTRAINT ck_emissor_ambiente CHECK (ambiente in ('homologacao','producao')), 
	CONSTRAINT ck_emissor_op_simp_nac CHECK (op_simp_nac in ('1','2','3')), 
	UNIQUE (cnpj)
);


CREATE TABLE IF NOT EXISTS dps_sequence (
	cnpj VARCHAR(14) NOT NULL, 
	serie VARCHAR(5) NOT NULL, 
	ambiente VARCHAR(16) NOT NULL, 
	ultimo_numero INTEGER DEFAULT '0' NOT NULL, 
	PRIMARY KEY (cnpj, serie, ambiente)
);


CREATE TABLE IF NOT EXISTS servicos (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	descricao_padrao TEXT NOT NULL, 
	codigo_lc116 VARCHAR(10), 
	c_trib_nac VARCHAR(6) NOT NULL, 
	c_trib_mun VARCHAR(3), 
	nbs VARCHAR(9), 
	aliquota_iss NUMERIC(5, 2), 
	iss_retido_padrao BOOLEAN DEFAULT false NOT NULL, 
	incluir_ibscbs BOOLEAN DEFAULT false NOT NULL, 
	c_ind_op VARCHAR(6), 
	cst_ibscbs VARCHAR(3), 
	c_class_trib VARCHAR(6), 
	tax_code_id INTEGER, 
	ativo BOOLEAN DEFAULT true NOT NULL, 
	criado_em TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	criado_por VARCHAR(255) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nome), 
	FOREIGN KEY(tax_code_id) REFERENCES tax_codes (id)
);

CREATE INDEX IF NOT EXISTS ix_servicos_tax_code_id ON servicos (tax_code_id);

CREATE TABLE IF NOT EXISTS tomadores (
	id SERIAL NOT NULL, 
	documento VARCHAR(14) NOT NULL, 
	nome VARCHAR(256) NOT NULL, 
	emails JSON NOT NULL, 
	inscricao_municipal VARCHAR(30), 
	optante_simples BOOLEAN DEFAULT false NOT NULL, 
	orgao_publico BOOLEAN DEFAULT false NOT NULL, 
	cep VARCHAR(8), 
	logradouro VARCHAR(256), 
	numero VARCHAR(20), 
	complemento VARCHAR(120), 
	bairro VARCHAR(120), 
	municipio_ibge VARCHAR(7), 
	uf VARCHAR(2), 
	origem VARCHAR(20) DEFAULT 'manual' NOT NULL, 
	ativo BOOLEAN DEFAULT true NOT NULL, 
	criado_em TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	atualizado_em TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (documento)
);


CREATE TABLE IF NOT EXISTS contrato_faturamento (
	contract_id VARCHAR(64) NOT NULL, 
	origem VARCHAR(16) DEFAULT 'legalone' NOT NULL, 
	tomador_id INTEGER, 
	servico_id INTEGER, 
	gera_rascunho_mensal BOOLEAN DEFAULT false NOT NULL, 
	atualizado_em TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (contract_id), 
	CONSTRAINT ck_cf_origem CHECK (origem in ('legalone','honorario')), 
	FOREIGN KEY(contract_id) REFERENCES contracts (contract_id), 
	FOREIGN KEY(tomador_id) REFERENCES tomadores (id), 
	FOREIGN KEY(servico_id) REFERENCES servicos (id)
);


CREATE TABLE IF NOT EXISTS faturas (
	id SERIAL NOT NULL, 
	contract_id VARCHAR(64) NOT NULL, 
	tomador_id INTEGER NOT NULL, 
	servico_id INTEGER NOT NULL, 
	competencia DATE NOT NULL, 
	descricao TEXT NOT NULL, 
	valor_bruto NUMERIC(12, 2) NOT NULL, 
	vencimento DATE, 
	parcela_num INTEGER DEFAULT '1' NOT NULL, 
	parcela_total INTEGER DEFAULT '1' NOT NULL, 
	origem VARCHAR(16) DEFAULT 'manual' NOT NULL, 
	status VARCHAR(16) DEFAULT 'rascunho' NOT NULL, 
	criada_por VARCHAR(255) NOT NULL, 
	aprovada_por VARCHAR(255), 
	criado_em TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	atualizado_em TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fatura_geracao UNIQUE (contract_id, competencia, origem, parcela_num), 
	CONSTRAINT ck_fatura_status CHECK (status in ('rascunho','aprovada','emitindo','emitida','cancelada')), 
	CONSTRAINT ck_fatura_origem CHECK (origem in ('manual','mensalidade','prolabore','exito','hora')), 
	CONSTRAINT ck_fatura_valor CHECK (valor_bruto > 0), 
	FOREIGN KEY(contract_id) REFERENCES contracts (contract_id), 
	FOREIGN KEY(tomador_id) REFERENCES tomadores (id), 
	FOREIGN KEY(servico_id) REFERENCES servicos (id)
);

CREATE INDEX IF NOT EXISTS ix_faturas_contract_id ON faturas (contract_id);
CREATE INDEX IF NOT EXISTS ix_faturas_status ON faturas (status);
CREATE INDEX IF NOT EXISTS ix_faturas_tomador_id ON faturas (tomador_id);

CREATE TABLE IF NOT EXISTS nfse_emitidas (
	id SERIAL NOT NULL, 
	fatura_id INTEGER NOT NULL, 
	status VARCHAR(16) DEFAULT 'processando' NOT NULL, 
	ambiente VARCHAR(16) NOT NULL, 
	cnpj_prestador VARCHAR(14) NOT NULL, 
	dps_serie VARCHAR(5) NOT NULL, 
	dps_numero INTEGER NOT NULL, 
	idempotency_key VARCHAR(80) NOT NULL, 
	chave_acesso VARCHAR(60), 
	numero_nfse VARCHAR(40), 
	valor_servicos NUMERIC(12, 2) NOT NULL, 
	iss NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
	retencoes JSON NOT NULL, 
	tomador_snapshot JSON NOT NULL, 
	servico_snapshot JSON NOT NULL, 
	xml_dps BYTEA, 
	xml_nfse BYTEA, 
	erro_codigo VARCHAR(20), 
	erro_mensagem TEXT, 
	nfse_recebida_id INTEGER, 
	emitida_em TIMESTAMP WITH TIME ZONE, 
	cancelada_em TIMESTAMP WITH TIME ZONE, 
	motivo_cancelamento TEXT, 
	emitida_por VARCHAR(255) NOT NULL, 
	criado_em TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	atualizado_em TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_nfse_emitida_status CHECK (status in ('processando','autorizada','rejeitada','cancelada')), 
	CONSTRAINT uq_nfse_emitida_dps UNIQUE (cnpj_prestador, ambiente, dps_serie, dps_numero), 
	FOREIGN KEY(fatura_id) REFERENCES faturas (id), 
	UNIQUE (idempotency_key), 
	FOREIGN KEY(nfse_recebida_id) REFERENCES nfse_recebidas (id)
);

CREATE INDEX IF NOT EXISTS ix_nfse_emitidas_fatura_id ON nfse_emitidas (fatura_id);
CREATE INDEX IF NOT EXISTS ix_nfse_emitidas_status ON nfse_emitidas (status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_nfse_emitida_viva ON nfse_emitidas (fatura_id) WHERE status in ('processando','autorizada');

CREATE TABLE IF NOT EXISTS nfse_emitida_eventos (
	id SERIAL NOT NULL, 
	nfse_emitida_id INTEGER NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	payload JSON NOT NULL, 
	criado_em TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(nfse_emitida_id) REFERENCES nfse_emitidas (id)
);

CREATE INDEX IF NOT EXISTS ix_nfse_emitida_eventos_nfse_emitida_id ON nfse_emitida_eventos (nfse_emitida_id);

COMMIT;
