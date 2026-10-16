-- Issue #126: aditivo, distrato e substabelecimento (documentos complementares).
-- Producao nao roda Alembic (sem tabela alembic_version): aplicar este SQL a mao, uma vez,
-- ANTES do deploy do codigo. Idempotente — pode rodar de novo sem efeito.
-- Equivale a alembic/versions/0015_documentos_complementares.py.

BEGIN;

ALTER TABLE contracts
    ADD COLUMN IF NOT EXISTS contrato_origem_id VARCHAR(64) REFERENCES contracts (contract_id);

CREATE INDEX IF NOT EXISTS ix_contracts_contrato_origem_id ON contracts (contrato_origem_id);

COMMIT;
