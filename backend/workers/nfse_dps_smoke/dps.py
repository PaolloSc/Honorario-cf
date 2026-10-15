"""DPS minima do leiaute nacional v1.01 (XSD oficial), sem prefixo de namespace.

So monta o XML. Assinatura em assinatura.py, envio em run.py. Os valores padrao
sao de teste (tomador ficticio, valor 1,00) e todos podem ser trocados."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from lxml import etree

NS = "http://www.sped.fazenda.gov.br/nfse"
BELO_HORIZONTE = "3106200"
# CNPJ de exemplo com digitos verificadores validos, sem dono conhecido.
TOMADOR_FICTICIO_CNPJ = "11222333000181"


@dataclass
class DpsParams:
    cnpj_prestador: str
    serie: str = "900"
    n_dps: int = 1
    valor: Decimal = Decimal("1.00")
    c_trib_nac: str = "171401"  # LC 116 item 17.14 (advocacia), desdobro 01
    descricao: str = "TESTE DE INTEGRACAO - SEM VALOR FISCAL"
    c_mun: str = BELO_HORIZONTE
    op_simp_nac: str = "1"  # 1 nao optante, 2 MEI, 3 ME/EPP
    reg_ap_trib_sn: str | None = None  # so ME/EPP (op_simp_nac=3); 1 tudo pelo SN, 2/3 ISS fora do SN. Padrao 1
    reg_esp_trib: str = "0"
    tp_ret_issqn: str = "1"  # 1 nao retido, 2 retido pelo tomador, 3 pelo intermediario
    p_tot_trib_sn: str = "0"  # so ME/EPP: % aproximado de tributos da aliquota do SN
    aliquota_iss: Decimal | None = None
    c_trib_mun: str | None = None  # 3 digitos; vira o 4o bloco do codigo de servico (17.14.01.001)
    competencia: date | None = None  # padrao: o dia da emissao
    im: str | None = None  # inscricao municipal do prestador (E0116 se o municipio exigir)
    nbs: str | None = None  # 9 digitos, sem pontos (E0322 se houver IBS/CBS)
    tomador_cnpj: str = TOMADOR_FICTICIO_CNPJ
    tomador_nome: str = "TOMADOR FICTICIO PARA TESTE LTDA"
    tomador_cpf: str | None = None  # se informado, vai no lugar do CNPJ do tomador
    tomador_end: dict | None = None  # cMun, CEP, xLgr, nro, xBairro (+ xCpl): so entra se completo
    ibscbs: bool = True
    c_ind_op: str = "100301"  # demais servicos onerosos (Anexo VII)
    cst: str = "000"
    c_class_trib: str = "000001"
    ver_aplic: str = "honorario-cf-smoke"
    agora: datetime | None = None


def regras_locais(p: DpsParams) -> list[str]:
    """Rejeicoes do Anexo I (v1.01) que da para evitar antes de enviar: o SEFIN devolve uma por vez."""
    erros = []
    sn_total = p.op_simp_nac == "3" and (p.reg_ap_trib_sn or "1") == "1"
    if p.op_simp_nac == "2" and p.reg_esp_trib != "0":
        erros.append("E0174: MEI exige regEspTrib=0")
    if sn_total and p.reg_esp_trib != "0":
        erros.append("E0175: ME/EPP com apuracao pelo SN (regApTribSN=1) exige regEspTrib=0")
    if sn_total and p.tp_ret_issqn == "1" and p.aliquota_iss is not None:
        erros.append("E0625: sem retencao de ISS (tpRetISSQN=1) nao se informa a aliquota; "
                     "para a nota com 5% retido use tp_ret_issqn=2")
    if sn_total and p.tp_ret_issqn in ("2", "3") and (p.aliquota_iss is None or p.aliquota_iss < Decimal("1.8")):
        erros.append("E0621: com ISS retido (tpRetISSQN=2/3), ME/EPP pelo SN informa a aliquota (minimo 1,80)")
    return erros


def id_dps(c_mun: str, cnpj: str, serie: str, n_dps: int) -> str:
    """'DPS' + municipio(7) + tipo de inscricao(1: 2=CNPJ) + CNPJ(14) + serie(5) + numero(15)."""
    return f"DPS{c_mun}2{cnpj}{int(serie):05d}{n_dps:015d}"


def _e(pai, nome, texto=None):
    el = etree.SubElement(pai, f"{{{NS}}}{nome}")
    if texto is not None:
        el.text = str(texto)
    return el


def montar_dps(p: DpsParams) -> bytes:
    # Brasilia, sem fracao de segundo, um minuto no passado: o SEFIN rejeita emissao "no futuro".
    agora = (p.agora or datetime.now(ZoneInfo("America/Sao_Paulo"))) - timedelta(seconds=60)
    dps = etree.Element(f"{{{NS}}}DPS", versao="1.01", nsmap={None: NS})
    inf = _e(dps, "infDPS")
    inf.set("Id", id_dps(p.c_mun, p.cnpj_prestador, p.serie, p.n_dps))
    _e(inf, "tpAmb", 2)  # producao restrita, fixo
    _e(inf, "dhEmi", agora.isoformat(timespec="seconds"))
    _e(inf, "verAplic", p.ver_aplic)
    _e(inf, "serie", p.serie)
    _e(inf, "nDPS", p.n_dps)
    _e(inf, "dCompet", (p.competencia or agora.date()).isoformat())
    _e(inf, "tpEmit", 1)
    _e(inf, "cLocEmi", p.c_mun)

    prest = _e(inf, "prest")
    _e(prest, "CNPJ", p.cnpj_prestador)
    if p.im:
        _e(prest, "IM", p.im)
    reg = _e(prest, "regTrib")
    _e(reg, "opSimpNac", p.op_simp_nac)
    if p.op_simp_nac == "3":  # E0166 se faltar; E0162 se vier para nao optante ou MEI
        _e(reg, "regApTribSN", p.reg_ap_trib_sn or "1")
    _e(reg, "regEspTrib", p.reg_esp_trib)

    toma = _e(inf, "toma")
    if p.tomador_cpf:
        _e(toma, "CPF", p.tomador_cpf)
    else:
        _e(toma, "CNPJ", p.tomador_cnpj)
    _e(toma, "xNome", p.tomador_nome)
    e = p.tomador_end or {}
    if all(e.get(k) for k in ("cMun", "CEP", "xLgr", "nro", "xBairro")):
        end = _e(toma, "end")
        nac = _e(end, "endNac")
        _e(nac, "cMun", e["cMun"])
        _e(nac, "CEP", e["CEP"])
        _e(end, "xLgr", e["xLgr"])
        _e(end, "nro", e["nro"])
        if e.get("xCpl"):
            _e(end, "xCpl", e["xCpl"])
        _e(end, "xBairro", e["xBairro"])

    serv = _e(inf, "serv")
    _e(_e(serv, "locPrest"), "cLocPrestacao", p.c_mun)
    c_serv = _e(serv, "cServ")
    _e(c_serv, "cTribNac", p.c_trib_nac)
    if p.c_trib_mun:
        _e(c_serv, "cTribMun", p.c_trib_mun)
    _e(c_serv, "xDescServ", p.descricao)
    if p.nbs:
        _e(c_serv, "cNBS", p.nbs)

    valores = _e(inf, "valores")
    _e(_e(valores, "vServPrest"), "vServ", f"{p.valor:.2f}")
    trib = _e(valores, "trib")
    trib_mun = _e(trib, "tribMun")
    _e(trib_mun, "tribISSQN", 1)
    _e(trib_mun, "tpRetISSQN", p.tp_ret_issqn)
    if p.aliquota_iss is not None:
        _e(trib_mun, "pAliq", f"{p.aliquota_iss:.2f}")
    tot = _e(trib, "totTrib")
    if p.op_simp_nac == "3":
        _e(tot, "pTotTribSN", p.p_tot_trib_sn)
    else:
        _e(tot, "indTotTrib", 0)

    if p.ibscbs:
        ib = _e(inf, "IBSCBS")
        _e(ib, "finNFSe", 0)
        _e(ib, "indFinal", 0)
        _e(ib, "cIndOp", p.c_ind_op)
        _e(ib, "indDest", 0)
        g = _e(_e(_e(ib, "valores"), "trib"), "gIBSCBS")
        _e(g, "CST", p.cst)
        _e(g, "cClassTrib", p.c_class_trib)

    return etree.tostring(dps, xml_declaration=True, encoding="UTF-8")
