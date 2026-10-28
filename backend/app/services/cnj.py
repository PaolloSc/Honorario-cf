"""Numero unico do CNJ (Res. CNJ 65/2008): NNNNNNN-DD.AAAA.J.TR.OOOO.

Tabela fixa, sem chamada externa: J (ramo da Justica) e TR (tribunal) dizem de onde e' o processo.
"""
import re
from dataclasses import dataclass
from typing import Optional

_MASCARA = re.compile(r"^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$")

JUSTICAS = {
    "1": "Supremo Tribunal Federal",
    "2": "Conselho Nacional de Justiça",
    "3": "Superior Tribunal de Justiça",
    "4": "Justiça Federal",
    "5": "Justiça do Trabalho",
    "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União",
    "8": "Justiça Estadual",
    "9": "Justiça Militar Estadual",
}

# Estados na ordem do campo TR (Justica Estadual e Eleitoral usam a mesma numeracao).
_UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
        "RJ", "RN", "RS", "RO", "RR", "SC", "SE", "SP", "TO"]

_SUPERIORES = {
    "1": "Supremo Tribunal Federal",
    "2": "Conselho Nacional de Justiça",
    "3": "Superior Tribunal de Justiça",
}


def _tribunal(j: str, tr: str) -> Optional[str]:
    n = int(tr)
    if j in _SUPERIORES:
        return _SUPERIORES[j] if n == 0 else None
    if j == "4":
        return f"Tribunal Regional Federal da {n}ª Região" if 1 <= n <= 6 else None
    if j == "5":
        return f"Tribunal Regional do Trabalho da {n}ª Região" if 1 <= n <= 24 else None
    if j == "6":
        return f"Tribunal Regional Eleitoral ({_UFS[n - 1]})" if 1 <= n <= 27 else None
    if j == "7":
        return f"{n}ª Circunscrição Judiciária Militar" if 1 <= n <= 12 else None
    if j == "8":
        return f"Tribunal de Justiça ({_UFS[n - 1]})" if 1 <= n <= 27 else None
    if j == "9":
        return {13: "Tribunal de Justiça Militar de MG", 21: "Tribunal de Justiça Militar do RS",
                26: "Tribunal de Justiça Militar de SP"}.get(n)
    return None


@dataclass(frozen=True)
class Cnj:
    numero: str  # com mascara
    ano: int
    justica: str
    tribunal: Optional[str]  # None: codigo TR que a tabela nao conhece


def normalizar(texto: str) -> Optional[str]:
    """Devolve o numero com mascara, aceitando-o com ou sem pontuacao; None se nao tiver 20 digitos."""
    digitos = re.sub(r"\D", "", texto or "")
    if len(digitos) != 20:
        return None
    return f"{digitos[:7]}-{digitos[7:9]}.{digitos[9:13]}.{digitos[13]}.{digitos[14:16]}.{digitos[16:]}"


def digito_valido(numero: str) -> bool:
    m = _MASCARA.match(numero)
    if not m:
        return False
    seq, dv, ano, j, tr, origem = m.groups()
    return 98 - (int(seq + ano + j + tr + origem + "00") % 97) == int(dv)


def decodificar(texto: str) -> Optional[Cnj]:
    """Numero valido (20 digitos e DD correto) -> ramo e tribunal; qualquer outra coisa -> None."""
    numero = normalizar(texto)
    if not numero or not digito_valido(numero):
        return None
    _, _, ano, j, tr, _ = _MASCARA.match(numero).groups()
    if j not in JUSTICAS:
        return None
    return Cnj(numero=numero, ano=int(ano), justica=JUSTICAS[j], tribunal=_tribunal(j, tr))
