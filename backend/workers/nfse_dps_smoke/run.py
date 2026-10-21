"""Smoke test: monta, assina e envia 1 DPS ao SEFIN Nacional, PRODUCAO RESTRITA.

    python -m workers.nfse_dps_smoke.run --cnpj 25463159000173
    python -m workers.nfse_dps_smoke.run --cnpj 25463159000173 --dry-run   # nao envia

Ambiente: NFSE_CERT_PFX_B64 e NFSE_CERT_PFX_SENHA (so via secrets). A saida tem
so o status HTTP, a chave de acesso ou os codigos e mensagens de rejeicao: nada
do certificado, da senha nem do corpo da DPS. O host e fixo no codigo e nao ha
opcao para trocar por producao."""
from __future__ import annotations

import argparse
import base64
import gzip
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from lxml import etree

from workers.nfse_adn.cert import CertificadoError, carregar_pfx, ssl_context_do_pfx

from .assinatura import PERFIS, assinar_dps
from .dps import DpsParams, id_dps, montar_dps, regras_locais
from .sefin import SEFIN_BASES, SEFIN_HOST, post_dps, uma_linha  # noqa: F401  (SEFIN_* reexportados)

# Parametros municipais (convenio, aliquotas...) do ADN, tambem so producao restrita.
PARAMETRIZACAO = "https://adn.producaorestrita.nfse.gov.br/parametrizacao"
_uma_linha = uma_linha


def enviar(http: httpx.Client, dps_assinado: bytes) -> int:
    """POST da DPS. 0 = nota gerada, 1 = rejeitada, 3 = sem resposta util."""
    r = post_dps(http, dps_assinado, avisar=print)
    print(f"POST {r.base}/nfse")
    print(f"HTTP {r.status}")
    if r.sucesso:
        print(f"NFS-e gerada. Chave de acesso: {r.chave}")
        return 0
    erros = r.erros
    for codigo, descricao in erros:
        print(f"rejeicao {uma_linha(codigo)}: {uma_linha(descricao)}")
    if not erros:
        # Sem JSON conhecido (ex.: pagina 403/404 do IIS): so o inicio do texto.
        print("resposta sem erros estruturados: " + uma_linha(r.texto)[:300])
    return 1 if erros else 3


def consultar(http: httpx.Client, c_mun: str, c_trib_nac: str, c_trib_mun: str | None, competencia: str) -> int:
    """GETs de parametrizacao do municipio (so leitura): convenio, aliquota, regimes especiais e
    retencoes para a competencia. O codigo de servico da API tem 9 digitos: cTribNac + 3 (000 ou cTribMun)."""
    n = c_trib_nac
    base = f"{n[0:2]}.{n[2:4]}.{n[4:6]}"
    codigos = [f"{base}.000"] + ([f"{base}.{c_trib_mun}"] if c_trib_mun and c_trib_mun != "000" else [])
    caminhos = [f"/{c_mun}/convenio"]
    for cod in codigos:
        caminhos += [f"/{c_mun}/{cod}/{competencia}/aliquota", f"/{c_mun}/{cod}/{competencia}/regimes_especiais"]
    caminhos.append(f"/{c_mun}/{competencia}/retencoes")
    for caminho in caminhos:
        r = http.get(f"{PARAMETRIZACAO}{caminho}")
        print(f"GET {caminho} -> HTTP {r.status_code}: {_uma_linha(r.text)[:700]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cnpj", required=True)
    ap.add_argument("--serie", default="900")
    ap.add_argument("--ndps", type=int, help="padrao: segundos desde 1970 (nao repete entre execucoes)")
    ap.add_argument("--valor", default="1.00")
    ap.add_argument("--c-trib-nac", default="171401")
    ap.add_argument("--op-simp-nac", default="1", choices=["1", "2", "3"])
    ap.add_argument("--reg-ap-trib-sn", choices=["1", "2", "3"], help="so ME/EPP (padrao 1: tudo pelo Simples)")
    ap.add_argument("--tp-ret-issqn", default="1", choices=["1", "2", "3"], help="1 nao retido, 2 retido pelo tomador")
    ap.add_argument("--p-tot-trib-sn", default="0", help="so ME/EPP, % aproximado de tributos (padrao 0)")
    ap.add_argument("--reg-esp-trib", default="0", choices=["0", "1", "2", "3", "4", "5", "6", "9"])
    ap.add_argument("--aliquota-iss")
    ap.add_argument("--c-trib-mun", help="codigo de tributacao municipal, 3 digitos (ex.: 001)")
    ap.add_argument("--competencia", help="AAAA-MM-DD (padrao: hoje, em Brasilia)")
    ap.add_argument("--consulta", action="store_true", help="so le os parametros do municipio, nao monta DPS")
    ap.add_argument("--im", help="inscricao municipal do prestador (nao ha padrao)")
    ap.add_argument("--nbs", help="codigo NBS, 9 digitos (nao ha padrao)")
    ap.add_argument("--tomador-cnpj", default="11222333000181")
    ap.add_argument("--sem-ibscbs", action="store_true")
    ap.add_argument("--tomador-cpf", help="usa CPF no lugar do CNPJ do tomador (11 digitos)")
    ap.add_argument("--tomador-end", help="CEP;logradouro;numero;bairro (municipio = o da emissao); E0239 exige com IBS/CBS")
    ap.add_argument("--descricao", help="xDescServ (padrao: texto de teste sem acento)")
    ap.add_argument("--ver-aplic", help="verAplic (padrao do smoke)")
    ap.add_argument("--assinatura", default="sha256", choices=sorted(PERFIS))
    ap.add_argument("--dry-run", action="store_true", help="monta e assina, nao envia")
    a = ap.parse_args(argv)

    cnpj = re.sub(r"\D", "", a.cnpj)
    try:
        pfx = base64.b64decode(os.environ["NFSE_CERT_PFX_B64"])
        senha = os.environ["NFSE_CERT_PFX_SENHA"]
        key, cert, extras = carregar_pfx(pfx, senha)
    except (CertificadoError, ValueError, KeyError) as e:
        # So o tipo do erro: a mensagem de KeyError/ValueError poderia ecoar valores.
        print(f"certificado ausente ou invalido ({type(e).__name__})")
        return 2
    vence = cert.not_valid_after_utc
    confere = cnpj in cert.subject.rfc4514_string()
    print(f"certificado: vence em {vence:%Y-%m-%d}"
          f"{' (VENCIDO)' if vence < datetime.now(timezone.utc) else ''}; "
          f"titular com o CNPJ informado: {'sim' if confere else 'NAO CONFERE'}; "
          f"intermediarios no pfx: {len(extras)}")

    if not confere:
        print("abortado: o certificado nao e do CNPJ informado (nada foi enviado)")
        return 2
    nbs = re.sub(r"\D", "", a.nbs or "")
    if a.nbs and len(nbs) != 9:
        print("abortado: --nbs deve ter 9 digitos (ex.: 1.1301.20.00 vira 113012000)")
        return 2

    if a.c_trib_mun and not re.fullmatch(r"\d{3}", a.c_trib_mun):
        print("abortado: --c-trib-mun deve ter 3 digitos (ex.: 001)")
        return 2
    try:
        competencia = date.fromisoformat(a.competencia) if a.competencia else None
    except ValueError:
        print("abortado: --competencia deve ser AAAA-MM-DD")
        return 2

    if a.consulta:
        dia = (competencia or datetime.now(ZoneInfo("America/Sao_Paulo")).date()).isoformat()
        try:
            with httpx.Client(verify=ssl_context_do_pfx(pfx, senha), timeout=60) as http:
                return consultar(http, "3106200", a.c_trib_nac, a.c_trib_mun, dia)
        except httpx.HTTPError as e:
            print(f"erro de rede/TLS: {type(e).__name__}: {e}")
            return 3

    n_dps = a.ndps or int(time.time())
    params = DpsParams(
        cnpj_prestador=cnpj, serie=a.serie, n_dps=n_dps, valor=Decimal(a.valor), c_trib_nac=a.c_trib_nac,
        op_simp_nac=a.op_simp_nac, reg_esp_trib=a.reg_esp_trib, tomador_cnpj=re.sub(r"\D", "", a.tomador_cnpj),
        aliquota_iss=Decimal(a.aliquota_iss) if a.aliquota_iss else None, ibscbs=not a.sem_ibscbs, c_trib_mun=a.c_trib_mun, competencia=competencia, im=a.im or None, nbs=nbs or None,
        reg_ap_trib_sn=a.reg_ap_trib_sn, tp_ret_issqn=a.tp_ret_issqn, p_tot_trib_sn=a.p_tot_trib_sn,
        **({"tomador_cpf": re.sub(r"\D", "", a.tomador_cpf)} if a.tomador_cpf else {}),
        **({"descricao": a.descricao} if a.descricao else {}),
        **({"tomador_end": dict(zip(("CEP", "xLgr", "nro", "xBairro"), (x.strip() for x in a.tomador_end.split(";"))), cMun="3106200")}
           if a.tomador_end else {}),
        **({"ver_aplic": a.ver_aplic} if a.ver_aplic else {}),
    )
    if erros := regras_locais(params):
        print("abortado: a DPS seria rejeitada pelas regras do Anexo I (nada foi enviado)")
        for e in erros:
            print(f"  {e}")
        return 2
    dps = montar_dps(params)
    assinado = assinar_dps(dps, key, cert, a.assinatura)
    print(f"DPS {id_dps('3106200', cnpj, a.serie, n_dps)} assinada ({a.assinatura}, {len(assinado)} bytes)")
    if a.dry_run:
        return 0

    ctx = ssl_context_do_pfx(pfx, senha)
    try:
        # httpx fala HTTP/1.1 por padrao: o SEFIN recusa HTTP/2 (HTTP_1_1_REQUIRED).
        with httpx.Client(verify=ctx, timeout=60) as http:
            return enviar(http, assinado)
    except httpx.HTTPError as e:
        print(f"erro de rede/TLS: {type(e).__name__}: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
