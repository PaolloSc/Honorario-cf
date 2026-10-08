from num2words import num2words
 
 
def valor_por_extenso(valor: float) -> str:
    """Convert a numeric value to Brazilian currency text.
 
    Example: 1500.50 -> 'mil e quinhentos reais e cinquenta centavos'
    """
    inteiro = int(valor)
    centavos = round((valor - inteiro) * 100)

    moeda = "real" if inteiro == 1 else "reais"
    sufixo_centavos = "centavo" if centavos == 1 else "centavos"

    if centavos == 0:
        extenso = num2words(inteiro, lang="pt_BR")
        return f"{extenso} {moeda}"

    extenso_inteiro = num2words(inteiro, lang="pt_BR")
    extenso_centavos = num2words(centavos, lang="pt_BR")

    if inteiro == 0:
        return f"{extenso_centavos} {sufixo_centavos}"

    return f"{extenso_inteiro} {moeda} e {extenso_centavos} {sufixo_centavos}"
 
 
def formatar_valor(valor: float) -> str:
    """Format value as BRL currency string: R$ 1.500,50"""
    formatted = f"{valor:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"
 
 
def valor_com_extenso(valor: float) -> str:
    """Format value as 'R$ 1.500,50 (mil e quinhentos reais e cinquenta centavos)'"""
    return f"{formatar_valor(valor)} ({valor_por_extenso(valor)})"

def formatar_percentual(value) -> str:
    """10 -> '10%', 10.5 -> '10,5%'. Aceita numero ou texto ('10.0', '10,5').

    Texto que nao e' numero volta como veio (so' acrescenta '%' se faltar).
    """
    try:
        num = float(str(value).strip().replace(",", ".")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        texto = str(value).strip()
        return texto if texto.endswith("%") else f"{texto}%"
    if num.is_integer():
        return f"{int(num)}%"
    return f"{num:.2f}".rstrip("0").rstrip(".").replace(".", ",") + "%"


def percentual_com_extenso(value) -> str:
    """10 -> '10% (dez por cento)', 2.25 -> '2,25% (dois vírgula vinte e cinco por cento)'."""
    num = round(float(value), 2)
    inteiro, _, dec = f"{num:.2f}".rstrip("0").rstrip(".").partition(".")
    extenso = num2words(int(inteiro), lang="pt_BR")
    if dec:
        zero = "zero " if dec.startswith("0") else ""  # 1,05 -> "um vírgula zero cinco"
        extenso += f" vírgula {zero}{num2words(int(dec), lang='pt_BR')}"
    return f"{formatar_percentual(num)} ({extenso} por cento)"
