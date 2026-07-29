"""Formatação da ficha de participação (uso interno do escritório).

A ficha é montada em três lugares (e-mail ao financeiro no envio, e-mail após
todas as assinaturas, rascunho no financeiro). Cada cópia envelheceu por conta
própria: a do DocuSeal ficou presa aos campos legados e imprimia a lista de
advogados como `['A', 'B']`. Formatar num lugar só evita esse descompasso.
"""
from __future__ import annotations

from typing import Any, Mapping


def valor_participacao(p: Mapping[str, Any]) -> tuple[str, str] | None:
    """(rótulo, valor) do critério da participação, ou None se não preenchido.

    Os campos estruturados (valor_tipo + o campo do tipo) vieram depois; o
    `percentual_ou_valor` continua atendendo contratos salvos antes disso.
    """
    tipo = p.get("valor_tipo")
    if tipo == "percentual" and p.get("valor_percentual"):
        return ("Percentual", f"{p['valor_percentual']}%")
    if tipo == "valor" and p.get("valor_monetario") is not None:
        valor = f"R$ {p['valor_monetario']:,.2f}"
        return ("Valor", valor.replace(",", "X").replace(".", ",").replace("X", "."))
    if tipo == "outro" and p.get("valor_outro"):
        return ("Critério", p["valor_outro"])
    if p.get("percentual_ou_valor"):
        return ("Percentual/Valor", p["percentual_ou_valor"])
    return None


def linhas_participacao(p: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Linhas (rótulo, valor) da ficha, omitindo o que não foi preenchido."""
    linhas: list[tuple[str, str]] = []

    if p.get("base_tipo") and p.get("base_label"):
        prefixo = "Escopo" if p["base_tipo"] == "escopo" else "Honorário"
        linhas.append(("Base", f"{prefixo} — {p['base_label']}"))

    valor = valor_participacao(p)
    if valor:
        linhas.append(valor)

    para_quem = p.get("para_quem") or []
    if isinstance(para_quem, str):  # formato antigo: um nome só
        para_quem = [para_quem] if para_quem.strip() else []
    if para_quem:
        linhas.append(("Para quem", ", ".join(para_quem)))

    for chave, rotulo in (
        ("natureza", "Natureza"),
        ("responsavel_captacao", "Resp. Captação"),
        ("responsavel_gestao", "Resp. Gestão"),
    ):
        if p.get(chave):
            linhas.append((rotulo, p[chave]))

    contatos = [
        ("contato_financeiro_nome", "Contato — Nome"),
        ("contato_financeiro_email", "Contato — E-mail"),
        ("contato_financeiro_telefone", "Contato — Telefone"),
    ]
    if any(p.get(c) for c, _ in contatos):
        linhas.extend((rotulo, p[c]) for c, rotulo in contatos if p.get(c))
    elif p.get("contato_financeiro_cliente"):
        linhas.append(("Contato Financeiro Cliente", p["contato_financeiro_cliente"]))

    return linhas
