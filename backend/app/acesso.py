"""Politica de acesso: quem pode o que, num so lugar.

Papeis sao um enum; cada papel tem um conjunto de capacidades. As rotas pedem a
CAPACIDADE (`exigir(Capacidade.X)` em app.auth, ou `pode(user, Capacidade.X)`), nunca comparam
o texto do papel. Para mudar quem pode o que, edita-se so a tabela CAPACIDADES_DO_PAPEL.

Sem FastAPI aqui: a matriz papel x capacidade testa-se sem HTTP.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class Papel(StrEnum):
    ADMIN = "admin"
    ADVOGADO = "advogado"
    FINANCEIRO = "financeiro"
    LEITOR = "leitor"  # somente leitura: toda escrita e' barrada em get_current_user


class Capacidade(StrEnum):
    ADMINISTRAR = "administrar"  # usuarios, credenciais, opcoes inativas
    OPERAR_FINANCEIRO = "operar_financeiro"  # participacoes, NFS-e, faturamento
    LER_FINANCEIRO = "ler_financeiro"  # ver notas emitidas (o leitor so le)
    VER_CONTRATOS_DE_TODOS = "ver_contratos_de_todos"  # sem ela, so' os que o usuario criou


CAPACIDADES_DO_PAPEL: dict[Papel, frozenset[Capacidade]] = {
    Papel.ADMIN: frozenset(Capacidade),
    Papel.FINANCEIRO: frozenset({Capacidade.OPERAR_FINANCEIRO, Capacidade.LER_FINANCEIRO}),
    Papel.LEITOR: frozenset({Capacidade.LER_FINANCEIRO}),
    Papel.ADVOGADO: frozenset(),
}

PAPEIS = tuple(p.value for p in Papel)
# O acesso de desenvolvimento (header X-Dev-User-Role) nunca emulou o leitor.
PAPEIS_DEV = tuple(p.value for p in Papel if p is not Papel.LEITOR)


class _ComPapel(Protocol):
    role: str


def capacidades_do(papel: str) -> frozenset[Capacidade]:
    """Papel desconhecido nao pode nada."""
    try:
        return CAPACIDADES_DO_PAPEL[Papel(papel)]
    except ValueError:
        return frozenset()


def pode(user: _ComPapel, capacidade: Capacidade) -> bool:
    return capacidade in capacidades_do(user.role)


def pode_acessar_contrato(user, contract) -> bool:
    """Admin ve todos; os demais, so' os contratos que criaram."""
    return pode(user, Capacidade.VER_CONTRATOS_DE_TODOS) or contract.created_by == user.email
