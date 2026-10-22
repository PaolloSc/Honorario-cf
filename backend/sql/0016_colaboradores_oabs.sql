-- OABs do cadastro de colaboradores (preenchem o substabelecimento).
-- Producao nao roda Alembic: aplicar este SQL a mao, uma vez, ANTES do deploy do codigo.
-- Idempotente. Equivale a alembic/versions/0016_colaboradores_oabs.py.

ALTER TABLE colaboradores ADD COLUMN IF NOT EXISTS oabs TEXT;
