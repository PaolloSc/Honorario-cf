from num2words import num2words
 
 
def valor_por_extenso(valor: float) -> str:
    """Convert a numeric value to Brazilian currency text.
 
    Example: 1500.50 -> 'mil e quinhentos reais e cinquenta centavos'
    """
    inteiro = int(valor)
    centavos = round((valor - inteiro) * 100)
 
    if centavos == 0:
        extenso = num2words(inteiro, lang="pt_BR")
        return f"{extenso} reais"
 
    extenso_inteiro = num2words(inteiro, lang="pt_BR")
    extenso_centavos = num2words(centavos, lang="pt_BR")
 
    if inteiro == 0:
        return f"{extenso_centavos} centavos"
 
    return f"{extenso_inteiro} reais e {extenso_centavos} centavos"
 
 
def formatar_valor(valor: float) -> str:
    """Format value as BRL currency string: R$ 1.500,50"""
    formatted = f"{valor:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"
 
 
def valor_com_extenso(valor: float) -> str:
    """Format value as 'R$ 1.500,50 (mil e quinhentos reais e cinquenta centavos)'"""
    return f"{formatar_valor(valor)} ({valor_por_extenso(valor)})"