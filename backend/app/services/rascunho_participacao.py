"""Rascunho da participacao que nasce junto com o contrato (percentuais zerados; o financeiro completa).

Deriva os campos da ficha a partir do que a pessoa preencheu no wizard.
"""
from __future__ import annotations

import re

from app.models.contract import ContratoRequest
from app.utils.participacao import valor_participacao, valor_participante


def _infer_tipo_honorario(data: ContratoRequest) -> str:
    """Olha todos escopos. Se >1 tipo distinto → 'misto'; senão usa o único; default 'mensalidade'."""
    tipos = set()
    for esc in data.escopos:
        for h in esc.honorarios:
            v = h.value if hasattr(h, "value") else str(h)
            # Mapeia para vocabulário do calculator
            if v == "hora_trabalhada":
                tipos.add("hora")
            elif v == "pro_labore":
                tipos.add("prolabore")
            elif v == "mensalidade":
                # Verifica subtipo advocacia_partido
                m = esc.mensalidade
                if m and getattr(m, "subtipo", None) and m.subtipo.value == "advocacia_partido":
                    tipos.add("partido")
                else:
                    tipos.add("mensalidade")
            elif v == "exito":
                tipos.add("exito")
            elif v == "permuta":
                tipos.add("exito")  # permuta segue regra de êxito (sem limite)
    if not tipos:
        return "mensalidade"
    if len(tipos) > 1:
        return "misto"
    return next(iter(tipos))


def _extract_cpf_cnpj(data: ContratoRequest) -> str | None:
    if not data.contratantes:
        return None
    first = data.contratantes[0]
    return getattr(first, "cpf", None) or getattr(first, "cnpj", None)


_EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
_PCT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def _parse_percentual(text: str | None) -> float:
    """Extrai primeiro numero seguido de % do texto livre. '10% de 5000' -> 10.0."""
    if not text:
        return 0.0
    m = _PCT_RE.search(text)
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return 0.0


def _parse_email(text: str | None) -> str | None:
    if not text:
        return None
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _map_natureza_wizard(natureza_text: str | None) -> tuple[bool, bool]:
    """Retorna (eh_captacao, eh_performance) com base no texto livre da wizard."""
    if not natureza_text:
        return False, False
    s = natureza_text.lower()
    eh_cap = "capta" in s
    eh_perf = "perform" in s
    if not eh_cap and not eh_perf:
        # Default: assume captacao se texto livre nao bate
        eh_cap = True
    return eh_cap, eh_perf

def campos_rascunho_participacao(data: ContratoRequest, user_email: str, user_name: str) -> dict:
    """Campos da ficha de participacao (rascunho) derivados do wizard; usado ao criar e ao editar."""
    tipo = _infer_tipo_honorario(data)
    participacao_data = data.participacao

    participantes_wizard = (participacao_data.participantes if participacao_data else None) or []

    # Parse valores da wizard
    pct = _parse_percentual(
        participacao_data.percentual_ou_valor if participacao_data else None
    )
    # Natureza vem agora por advogado; usa a do primeiro participante como base.
    primeira_natureza = participantes_wizard[0].natureza if participantes_wizard else None
    eh_cap, eh_perf = _map_natureza_wizard(primeira_natureza)
    pct_captacao = pct if eh_cap else 0.0
    pct_performance = pct if eh_perf else 0.0

    # Email: prioriza campo estruturado novo, fallback parse do legado, fallback user.
    email_novo = (participacao_data.contato_financeiro_email or "").strip() if participacao_data else ""
    email_wizard = email_novo or _parse_email(
        participacao_data.contato_financeiro_cliente if participacao_data else None
    )
    beneficiario_email = email_wizard or user_email
    # Nome: junta os nomes de todos os participantes. Fallback user_name.
    beneficiario_nome = (
        ", ".join(p.nome for p in participantes_wizard) if participantes_wizard else user_name
    )

    # Backend natureza = contratual/societario (campo legal, nao wizard)
    natureza_val = "contratual"

    # Motivos: usa texto da wizard quando aplicável
    motivo_cap = (
        participacao_data.responsavel_captacao
        if participacao_data and pct_captacao > 0 and participacao_data.responsavel_captacao
        else None
    )
    motivo_perf = (
        participacao_data.responsavel_gestao
        if participacao_data and pct_performance > 0 and participacao_data.responsavel_gestao
        else None
    )

    obs_extra = ""
    if participacao_data:
        # Mesma formatacao da ficha (R$ 5.000,00, nao R$ 5000.00).
        valor_geral = valor_participacao(participacao_data.model_dump())
        valor_str = valor_geral[1] if valor_geral else "-"
        participantes_str = "; ".join(
            f"{p.nome} ({p.natureza or '-'}, {valor_participante(p.model_dump()) or 'geral'})"
            for p in participantes_wizard
        ) or "-"
        obs_extra = (
            f"Rascunho automatico do wizard. "
            f"Captacao responsavel: {participacao_data.responsavel_captacao or '-'} · "
            f"Gestao: {participacao_data.responsavel_gestao or '-'} · "
            f"Valor wizard: {valor_str} · "
            f"Participantes: {participantes_str}"
        )
    else:
        obs_extra = "Rascunho automatico do wizard."

    return {
        "beneficiario_email": beneficiario_email,
        "beneficiario_nome": beneficiario_nome or "",
        "tipo_honorario": tipo,
        "percentual_captacao": pct_captacao,
        "percentual_performance": pct_performance,
        "motivo_captacao": motivo_cap,
        "motivo_performance": motivo_perf,
        "natureza": natureza_val,
        "cliente_cpf_cnpj": _extract_cpf_cnpj(data),
        "observacoes": obs_extra,
    }
