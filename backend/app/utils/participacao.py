"""Formatação da ficha de participação (uso interno do escritório).

A ficha é montada em três lugares (e-mail ao financeiro no envio, e-mail após
todas as assinaturas, rascunho no financeiro). Cada cópia envelheceu por conta
própria: a do DocuSeal ficou presa aos campos legados e imprimia a lista de
advogados como `['A', 'B']`. Formatar num lugar só evita esse descompasso.
"""
from __future__ import annotations

from typing import Any, Mapping


def _reais(valor: float) -> str:
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def valor_participante(participante: Mapping[str, Any]) -> str | None:
    """Valor proprio de um advogado (sobrescreve o geral), ou None se nao preenchido.

    Sem valor_tipo o wizard mostra "percentual" marcado, entao esse e' o padrao.
    """
    tipo = participante.get("valor_tipo") or "percentual"
    if tipo == "percentual" and participante.get("percentual"):
        return f"{participante['percentual']}%"
    if tipo == "valor" and participante.get("valor_monetario") is not None:
        return _reais(participante["valor_monetario"])
    if tipo == "outro" and participante.get("valor_outro"):
        return participante["valor_outro"]
    return None


def valor_participacao(p: Mapping[str, Any]) -> tuple[str, str] | None:
    """(rótulo, valor) do critério da participação, ou None se não preenchido.

    Os campos estruturados (valor_tipo + o campo do tipo) vieram depois; o
    `percentual_ou_valor` continua atendendo contratos salvos antes disso.
    """
    tipo = p.get("valor_tipo")
    if tipo == "percentual" and p.get("valor_percentual"):
        return ("Percentual", f"{p['valor_percentual']}%")
    if tipo == "valor" and p.get("valor_monetario") is not None:
        return ("Valor", _reais(p["valor_monetario"]))
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

    valor_geral = valor_participacao(p)
    if valor_geral:
        linhas.append(valor_geral)

    # Cada advogado com natureza/percentual proprios. Contratos antigos gravaram
    # para_quem (lista de nomes) + uma unica natureza — cai aqui como fallback.
    participantes = p.get("participantes") or []
    if participantes:
        for participante in participantes:
            nome = participante.get("nome", "")
            if not nome:
                continue
            natureza = participante.get("natureza", "")
            # Sem valor proprio vale o geral — dito por extenso pra ninguem deduzir.
            valor = valor_participante(participante) or (
                f"{valor_geral[1]} (geral)" if valor_geral else ""
            )
            texto = ", ".join(v for v in (natureza, valor) if v)
            linhas.append((f"Para quem — {nome}", texto or "—"))
    else:
        para_quem = p.get("para_quem") or []
        if isinstance(para_quem, str):  # formato antigo: um nome só
            para_quem = [para_quem] if para_quem.strip() else []
        if para_quem:
            linhas.append(("Para quem", ", ".join(para_quem)))
        if p.get("natureza"):
            linhas.append(("Natureza", p["natureza"]))

    for chave, rotulo in (
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

    # Cadastro no Legal One. Fica aqui, e nao so no e-mail, para as tres copias da
    # ficha (envio, pos-assinatura e rascunho do financeiro) nascerem iguais.
    if p.get("categoria_cliente"):
        linhas.append(("Categoria do cliente", p["categoria_cliente"]))
    valores = p.get("listas_transmissao") or []
    if isinstance(valores, str):  # formato antigo: um valor so
        valores = [valores] if valores.strip() else []
    if valores:
        linhas.append(("Lista de transmissão", ", ".join(valores)))

    return linhas
