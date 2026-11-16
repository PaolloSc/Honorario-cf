"""testemunhas.cpf

CPF da testemunha (so' digitos), impresso sob a assinatura dela no contrato.
Nulo em quem ja' estava cadastrado; o cadastro novo exige.

Revision ID: 0018_testemunhas_cpf
Revises: 0017_pagamentos_numeric
Create Date: 2026-11-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_testemunhas_cpf"
down_revision = "0017_pagamentos_numeric"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("testemunhas", sa.Column("cpf", sa.String(length=11), nullable=True))


def downgrade() -> None:
    op.drop_column("testemunhas", "cpf")
