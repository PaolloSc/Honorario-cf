"""Entrypoint do worker NFS-e (GitHub Actions runner).

Uso:
    python -m workers.nfse_scraper.run --cnpj 12345678000199
    python -m workers.nfse_scraper.run --cnpj 12345678000199 --inicio 2026-05-01 --fim 2026-05-31
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

from .client import (
    BHISSClient,
    CaptchaError,
    LayoutChangedError,
    LoginError,
    PortalDownError,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nfse-worker")


async def _main(cnpj: str, inicio: date, fim: date, api_url: str, token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.get(f"{api_url}/api/nfse/credenciais/{cnpj}", headers=headers)
        if response.status_code != 200:
            log.error("falha ao obter credencial: %s %s", response.status_code, response.text)
            await _report(
                http,
                api_url,
                token,
                cnpj,
                "erro_login",
                motivo=f"credencial unreachable: {response.status_code}",
            )
            return 2
        cred = response.json()

        screenshots = Path("screenshots")
        try:
            async with BHISSClient(screenshot_dir=screenshots) as client:
                await client.login(cred["login"], cred["senha"])
                xmls = await client.fetch_nfse_periodo(inicio, fim)
        except LoginError as e:
            await _report(http, api_url, token, cnpj, "erro_login", motivo=str(e))
            return 3
        except CaptchaError as e:
            await _report(http, api_url, token, cnpj, "captcha", motivo=str(e))
            return 4
        except LayoutChangedError as e:
            await _report(http, api_url, token, cnpj, "layout", motivo=str(e))
            return 5
        except PortalDownError as e:
            await _report(http, api_url, token, cnpj, "portal_down", motivo=str(e))
            return 6

        payload = {
            "cnpj_prestador": cnpj,
            "periodo_inicio": inicio.isoformat(),
            "periodo_fim": fim.isoformat(),
            "origem": "cron",
            "disparado_por": os.getenv("GITHUB_TRIGGERING_ACTOR", "gh-actions"),
            "xmls_b64": [base64.b64encode(xml).decode() for xml in xmls],
        }
        response = await http.post(f"{api_url}/api/nfse/ingest", headers=headers, json=payload, timeout=120)
        if response.status_code >= 400:
            log.error("ingest falhou: %s %s", response.status_code, response.text)
            return 7
        log.info("ingest ok: %s", response.json())
        return 0


async def _report(http, api_url: str, token: str, cnpj: str, status: str, motivo: str) -> None:
    try:
        await http.post(
            f"{api_url}/api/nfse/sync-status",
            headers={"Authorization": f"Bearer {token}"},
            params={"cnpj_prestador": cnpj, "status": status, "motivo": motivo},
        )
    except Exception as e:
        log.error("falha ao reportar status: %s", e)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cnpj", required=True)
    parser.add_argument("--inicio", help="YYYY-MM-DD (default: ontem)")
    parser.add_argument("--fim", help="YYYY-MM-DD (default: hoje)")
    args = parser.parse_args()

    api_url = os.environ["HONORARIO_API_URL"].rstrip("/")
    token = os.environ["NFSE_WORKER_TOKEN"]

    fim = date.fromisoformat(args.fim) if args.fim else date.today()
    inicio = date.fromisoformat(args.inicio) if args.inicio else (fim - timedelta(days=1))

    code = asyncio.run(_main(args.cnpj, inicio, fim, api_url, token))
    sys.exit(code)


if __name__ == "__main__":
    main()
