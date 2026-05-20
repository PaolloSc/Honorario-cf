"""Cálculo de participações internas em honorários contratuais.

Regras (vigência a partir de 2024-08-01, sem retroatividade para valores anteriores a 31/07/2024;
não se aplicam a parceiros técnicos/comerciais).

- Aplica-se apenas a honorários contratuais (sucumbenciais excluídos). Se acordo/alvará
  não discriminar verbas, considera-se 50% contratual / 50% sucumbencial.
- Captação até 20%: novo contrato com CPF/CNPJ sem contrato vigente e sem faturamento
  nos últimos 36 meses.
- Performance até 20%: atuação excepcional reconhecida OU nova área/serviço aprovada
  pelos sócios.
- Captação + Performance combinados: até 40%.
- Base de cálculo: valor líquido recebido pelo escritório.
- Limite temporal por tipo (a contar da data de início da participação):
    hora        → 3 anos
    partido     → 2 anos
    mensalidade → 2 anos
    êxito       → sem limite
    prolabore   → sem limite
    misto       → aplica regra de cada subtipo (caller passa subtipo explícito).
- Participação só é devida enquanto houver vínculo ativo (contratual ou societário).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

DATA_VIGENCIA = date(2024, 8, 1)
DATA_CORTE_RETROATIVA = date(2024, 7, 31)

LIMITE_CAPTACAO = 20.0
LIMITE_PERFORMANCE = 20.0
LIMITE_COMBO = 40.0

LIMITES_TEMPORAIS_ANOS: dict[str, Optional[int]] = {
    "hora": 3,
    "partido": 2,
    "mensalidade": 2,
    "exito": None,
    "prolabore": None,
    "misto": None,  # caller deve fornecer subtipo
}

TIPOS_VALIDOS = set(LIMITES_TEMPORAIS_ANOS.keys())


class ParticipacaoInvalidaError(ValueError):
    pass


@dataclass
class ValidacaoParticipacao:
    ok: bool
    erros: list[str]


def validar_percentuais(captacao: float, performance: float) -> ValidacaoParticipacao:
    erros: list[str] = []
    if captacao < 0 or performance < 0:
        erros.append("Percentuais não podem ser negativos.")
    if captacao > LIMITE_CAPTACAO:
        erros.append(f"Captação não pode exceder {LIMITE_CAPTACAO:.0f}%.")
    if performance > LIMITE_PERFORMANCE:
        erros.append(f"Performance não pode exceder {LIMITE_PERFORMANCE:.0f}%.")
    if (captacao + performance) > LIMITE_COMBO:
        erros.append(
            f"Soma de Captação + Performance não pode exceder {LIMITE_COMBO:.0f}%."
        )
    return ValidacaoParticipacao(ok=not erros, erros=erros)


def validar_data_inicio(data_inicio: date) -> ValidacaoParticipacao:
    erros: list[str] = []
    if data_inicio < DATA_VIGENCIA:
        erros.append(
            "Regras de participação vigentes a partir de 2024-08-01. "
            "Valores anteriores a 31/07/2024 não são afetados (sem retroatividade)."
        )
    return ValidacaoParticipacao(ok=not erros, erros=erros)


def validar_tipo_honorario(tipo: str) -> ValidacaoParticipacao:
    if tipo not in TIPOS_VALIDOS:
        return ValidacaoParticipacao(
            ok=False,
            erros=[f"Tipo inválido. Use um de: {sorted(TIPOS_VALIDOS)}"],
        )
    return ValidacaoParticipacao(ok=True, erros=[])


def validar_participacao(
    tipo_honorario: str,
    captacao: float,
    performance: float,
    data_inicio: date,
) -> ValidacaoParticipacao:
    erros: list[str] = []
    for v in (
        validar_tipo_honorario(tipo_honorario),
        validar_percentuais(captacao, performance),
        validar_data_inicio(data_inicio),
    ):
        erros.extend(v.erros)
    return ValidacaoParticipacao(ok=not erros, erros=erros)


@dataclass
class ResultadoCalculo:
    valor_participacao: float
    dentro_limite_temporal: bool
    vinculo_ativo: bool
    motivo_zerado: Optional[str] = None


def calcular_valor_participacao(
    *,
    valor_liquido_recebido: float,
    percentual_captacao: float,
    percentual_performance: float,
    tipo_honorario: str,
    data_inicio_participacao: date,
    data_recebimento: date,
    vinculo_ativo: bool,
    data_fim_vinculo: Optional[date] = None,
    eh_contratual: bool = True,
) -> ResultadoCalculo:
    """Calcula o valor da participação para um recebimento líquido.

    - eh_contratual=False zera (sucumbenciais excluídos).
    - Se vínculo encerrado antes do recebimento → zero.
    - Se data_recebimento ultrapassou o limite temporal do tipo → zero.
    - Se data_recebimento < 2024-08-01 → zero (não retroativo).
    """
    if not eh_contratual:
        return ResultadoCalculo(0.0, False, vinculo_ativo, "Honorário não-contratual (sucumbencial)")

    if data_recebimento <= DATA_CORTE_RETROATIVA:
        return ResultadoCalculo(0.0, False, vinculo_ativo, "Recebimento anterior à vigência (31/07/2024)")

    if not vinculo_ativo:
        return ResultadoCalculo(0.0, True, False, "Vínculo encerrado")

    if data_fim_vinculo and data_recebimento > data_fim_vinculo:
        return ResultadoCalculo(0.0, True, False, "Recebimento após término do vínculo")

    limite_anos = LIMITES_TEMPORAIS_ANOS.get(tipo_honorario)
    dentro_limite = True
    if limite_anos is not None:
        try:
            data_limite = data_inicio_participacao.replace(
                year=data_inicio_participacao.year + limite_anos
            )
        except ValueError:
            # 29/02 em ano não-bissexto
            data_limite = data_inicio_participacao.replace(
                year=data_inicio_participacao.year + limite_anos, day=28
            )
        if data_recebimento > data_limite:
            dentro_limite = False
            return ResultadoCalculo(
                0.0,
                False,
                True,
                f"Limite temporal de {limite_anos} ano(s) ultrapassado para tipo '{tipo_honorario}'",
            )

    percentual_total = (percentual_captacao or 0.0) + (percentual_performance or 0.0)
    valor = round(valor_liquido_recebido * percentual_total / 100.0, 2)
    return ResultadoCalculo(valor, dentro_limite, True, None)


def split_contratual_sucumbencial(
    valor_bruto: float,
    discriminado: bool,
    valor_contratual_informado: Optional[float] = None,
) -> tuple[float, float]:
    """Se não discriminado, divide 50/50 entre contratual e sucumbencial."""
    if discriminado and valor_contratual_informado is not None:
        contratual = valor_contratual_informado
        sucumbencial = max(valor_bruto - contratual, 0.0)
        return (round(contratual, 2), round(sucumbencial, 2))
    metade = round(valor_bruto / 2.0, 2)
    return (metade, round(valor_bruto - metade, 2))
