"""Seletores CSS/XPath para portal BHISS Digital.

Centralizado para facilitar manutencao quando o portal muda.
Cada constante vem com comentario e timestamp de ultima validacao.
"""
# Ultima validacao: 2026-05-20

LOGIN_URL = "https://bhissdigital.pbh.gov.br/nfse/"

# Login form
SEL_LOGIN_USER = "input[name='usuario']"
SEL_LOGIN_PASS = "input[name='senha']"
SEL_LOGIN_SUBMIT = "button[type='submit'], input[type='submit']"
SEL_LOGIN_ERROR = ".mensagem-erro, .alert-danger"

# CAPTCHA
SEL_CAPTCHA_IMG = "img[alt*='captcha' i], #captcha img, .captcha img"

# Pos-login: identificar sucesso
SEL_DASHBOARD = "nav.menu-principal, #menu-nfse, a[href*='consultaNFSe']"

# Consulta NFS-e
SEL_MENU_CONSULTA = "a[href*='consultaNFSe'], a:has-text('Consultar')"
SEL_FILTRO_DATA_INI = "input[name*='dataInicio']"
SEL_FILTRO_DATA_FIM = "input[name*='dataFim']"
SEL_BTN_FILTRAR = "button:has-text('Filtrar'), input[value='Filtrar']"

# Exportacao XML
SEL_BTN_EXPORTAR_XML = "a:has-text('Exportar XML'), button:has-text('XML')"
