"""Entrypoint do worker NFS-e via ADN (GitHub Actions).

Uso:
    python -m workers.nfse_adn.run --cnpj 25463159000173            # so lista (dry-run)
    python -m workers.nfse_adn.run --cnpj 25463159000173 --ingerir  # grava no Honorario

Ambiente: NFSE_CERT_PFX_B64, NFSE_CERT_PFX_SENHA, NFSE_ADN_BASE_URL (padrao:
homologacao) e, com --ingerir, HONORARIO_API_URL e NFSE_WORKER_TOKEN.
--ingerir exige NFSE_ADN_BASE_URL igual a URL de producao.
Os valores do certificado nunca vao para log."""
from __future__ import annotations

import argparse
import base64
import logging
import os
import sys
from datetime import date

import httpx

from .cert import CertificadoError, ssl_context_do_pfx
from .client import ADNError, lotes


ADN_PRODUCAO = "https://adn.nfse.gov.br/contribuintes"
ADN_HOMOLOGACAO = "https://adn.producaorestrita.nfse.gov.br/contribuintes"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nfse-adn")


def _report(hon: httpx.Client | None, cnpj: str, status: str, motivo: str) -> None:
    if hon is None:
        return
    try:
        hon.post("/api/nfse/sync-status", params={"cnpj_prestador": cnpj, "status": status, "motivo": motivo})
    except httpx.HTTPError as e:
        log.error("falha ao reportar status: %s", e)


def executar(cnpj: str, adn: httpx.Client, hon: httpx.Client | None, nsu: int | None = None) -> int:
    """Baixa do ADN a partir do ultimo NSU ingerido. hon=None: dry-run, so registra no log."""
    try:
        if nsu is None:
            nsu = 0
            if hon is not None:
                r = hon.get("/api/nfse/adn/ultimo-nsu", params={"cnpj": cnpj})
                r.raise_for_status()
                nsu = r.json()["ultimo_nsu"]
        log.info("ADN %s a partir do NSU %s", adn.base_url, nsu)
        for lote in lotes(adn, nsu):
            ultimo = lote[-1][0]
            if hon is None:
                log.info("dry-run: %d documento(s), NSU %d a %d", len(lote), lote[0][0], ultimo)
                continue
            hoje = date.today().isoformat()
            r = hon.post("/api/nfse/ingest", timeout=120, json={
                "cnpj_prestador": cnpj,
                "periodo_inicio": hoje,
                "periodo_fim": hoje,
                "origem": "cron",
                "disparado_por": os.getenv("GITHUB_TRIGGERING_ACTOR", "gh-actions"),
                "xmls_b64": [base64.b64encode(xml).decode() for _, xml in lote],
                "ultimo_nsu": ultimo,
            })
            if r.status_code >= 400:
                log.error("ingest falhou: %s %s", r.status_code, r.text)
                return 4
            log.info("ingest ok ate NSU %d: %s", ultimo, r.json())
    except (ADNError, httpx.HTTPError) as e:
        log.error("erro no ADN: %s", e)
        _report(hon, cnpj, "erro_adn", str(e)[:500])
        return 3
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cnpj", required=True)
    parser.add_argument("--ingerir", action="store_true", help="grava no Honorario (sem isso: dry-run)")
    parser.add_argument("--nsu", type=int, help="NSU inicial (padrao: ultimo ingerido, ou 0 no dry-run)")
    args = parser.parse_args()
    cnpj = "".join(ch for ch in args.cnpj if ch.isdigit())
    base = (os.getenv("NFSE_ADN_BASE_URL") or ADN_HOMOLOGACAO).rstrip("/")
    if args.ingerir and base != ADN_PRODUCAO:
        # Trava tambem aqui, nao so no workflow: nota de homologacao nunca
        # entra no Honorario, nem rodando o worker a mao.
        log.error("--ingerir so com NFSE_ADN_BASE_URL=%s (atual: %s)", ADN_PRODUCAO, base)
        sys.exit(2)

    hon = None
    if args.ingerir:
        hon = httpx.Client(
            base_url=os.environ["HONORARIO_API_URL"].rstrip("/"),
            headers={"Authorization": f"Bearer {os.environ['NFSE_WORKER_TOKEN']}"},
            timeout=30,
        )
    try:
        ctx = ssl_context_do_pfx(
            base64.b64decode(os.environ["NFSE_CERT_PFX_B64"]), os.environ["NFSE_CERT_PFX_SENHA"]
        )
    except (CertificadoError, ValueError, KeyError) as e:
        # So o tipo do erro: a mensagem de KeyError/ValueError poderia ecoar valores.
        log.error("certificado ausente ou invalido (%s)", type(e).__name__)
        _report(hon, cnpj, "erro_certificado", "certificado .pfx ausente, invalido ou senha incorreta")
        sys.exit(2)

    with httpx.Client(base_url=base, verify=ctx, timeout=60) as adn:
        code = executar(cnpj, adn, hon, args.nsu)
    if hon is not None:
        hon.close()
    sys.exit(code)


if __name__ == "__main__":
    main()
