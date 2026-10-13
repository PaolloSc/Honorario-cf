"""NFS-e pelo ADN (padrao nacional): direcao, chave de acesso e ultimo NSU

Revision ID: 0013_nfse_adn
Revises: 0012_contract_drafts
Create Date: 2026-10-08

Producao nao tem alembic_version: aplicar o DDL equivalente a mao (ver PR).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_nfse_adn"
down_revision = "0012_contract_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nfse_recebidas") as t:
        t.add_column(sa.Column("direcao", sa.String(10), nullable=False, server_default="emitida"))
        t.add_column(sa.Column("chave_acesso", sa.String(50), nullable=True))
        t.create_unique_constraint("uq_nfse_chave_acesso", ["chave_acesso"])
        t.drop_constraint("uq_nfse_chave", type_="unique")
        t.create_unique_constraint("uq_nfse_chave", ["cnpj_prestador", "numero", "serie", "direcao"])
    op.add_column("sync_jobs", sa.Column("ultimo_nsu", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("sync_jobs", "ultimo_nsu")
    with op.batch_alter_table("nfse_recebidas") as t:
        t.drop_constraint("uq_nfse_chave", type_="unique")
        t.create_unique_constraint("uq_nfse_chave", ["cnpj_prestador", "numero", "serie"])
        t.drop_constraint("uq_nfse_chave_acesso", type_="unique")
        t.drop_column("chave_acesso")
        t.drop_column("direcao")
