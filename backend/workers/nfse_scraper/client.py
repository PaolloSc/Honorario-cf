"""Cliente headless Playwright para portal BHISS Digital."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import date
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    Page,
    TimeoutError as PWTimeout,
    async_playwright,
)

from . import selectors as S


log = logging.getLogger(__name__)


class ScraperError(Exception):
    pass


class LoginError(ScraperError):
    pass


class CaptchaError(ScraperError):
    pass


class LayoutChangedError(ScraperError):
    pass


class PortalDownError(ScraperError):
    pass


class BHISSClient:
    def __init__(self, screenshot_dir: Path | None = None) -> None:
        self.screenshot_dir = screenshot_dir or Path("screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._pw = None
        self._browser = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> "BHISSClient":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = await self._browser.new_context(
            user_agent="Mozilla/5.0 honorario-cf-nfse-sync",
            locale="pt-BR",
        )
        self._page = await ctx.new_page()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def _human_delay(self) -> None:
        await asyncio.sleep(random.uniform(0.8, 1.5))

    async def _shot(self, name: str) -> Path:
        path = self.screenshot_dir / f"{name}.png"
        if self._page:
            try:
                await self._page.screenshot(path=str(path), full_page=True)
            except Exception:
                pass
        return path

    async def login(self, login: str, senha: str) -> None:
        assert self._page
        try:
            await self._page.goto(S.LOGIN_URL, timeout=30_000)
        except PWTimeout as e:
            await self._shot("portal_down")
            raise PortalDownError(str(e)) from e

        if await self._page.locator(S.SEL_CAPTCHA_IMG).count() > 0:
            await self._shot("captcha_pre_login")
            raise CaptchaError("CAPTCHA presente na tela de login")

        try:
            await self._page.fill(S.SEL_LOGIN_USER, login)
            await self._human_delay()
            await self._page.fill(S.SEL_LOGIN_PASS, senha)
            await self._human_delay()
            await self._page.click(S.SEL_LOGIN_SUBMIT)
        except PWTimeout as e:
            await self._shot("login_form_layout")
            raise LayoutChangedError(f"form login: {e}") from e

        try:
            await self._page.wait_for_selector(S.SEL_DASHBOARD, timeout=20_000)
        except PWTimeout:
            err_count = await self._page.locator(S.SEL_LOGIN_ERROR).count()
            if err_count > 0:
                await self._shot("login_invalid")
                raise LoginError("login/senha invalidos")
            if await self._page.locator(S.SEL_CAPTCHA_IMG).count() > 0:
                await self._shot("captcha_post_login")
                raise CaptchaError("CAPTCHA apos submit")
            await self._shot("login_no_dashboard")
            raise LayoutChangedError("dashboard nao detectado apos login")

    async def fetch_nfse_periodo(self, ini: date, fim: date) -> list[bytes]:
        assert self._page
        try:
            await self._page.click(S.SEL_MENU_CONSULTA)
            await self._human_delay()
            await self._page.fill(S.SEL_FILTRO_DATA_INI, ini.strftime("%d/%m/%Y"))
            await self._page.fill(S.SEL_FILTRO_DATA_FIM, fim.strftime("%d/%m/%Y"))
            await self._human_delay()
            await self._page.click(S.SEL_BTN_FILTRAR)
            await self._page.wait_for_load_state("networkidle", timeout=30_000)
        except PWTimeout as e:
            await self._shot("consulta_layout")
            raise LayoutChangedError(f"menu consulta: {e}") from e

        try:
            async with self._page.expect_download(timeout=60_000) as download_info:
                await self._page.click(S.SEL_BTN_EXPORTAR_XML)
            download = await download_info.value
            path = await download.path()
        except PWTimeout as e:
            await self._shot("export_xml")
            raise LayoutChangedError(f"exportar XML: {e}") from e

        if not path:
            return []

        data = Path(path).read_bytes()
        if data[:2] == b"PK":
            from io import BytesIO
            from zipfile import ZipFile

            xmls: list[bytes] = []
            with ZipFile(BytesIO(data)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".xml"):
                        xmls.append(zf.read(name))
            return xmls
        return [data]
