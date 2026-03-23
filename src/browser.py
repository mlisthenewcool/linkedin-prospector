"""Lancement Playwright + stealth + session persistante."""

from __future__ import annotations

import random
from datetime import UTC, datetime

import structlog
from playwright.async_api import Browser, BrowserContext, Page, ViewportSize, async_playwright
from playwright_stealth import Stealth

from src.config import SESSION_STATE_PATH, Config

logger = structlog.get_logger()


class BrowserManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._started_at: datetime | None = None
        self._max_session_minutes: int = random.randint(45, 90)

    async def start(self) -> Page:
        """Lance le navigateur avec stealth et session persistante."""
        self._started_at = datetime.now(UTC)
        self._playwright = await async_playwright().start()

        session_path = SESSION_STATE_PATH
        session_path.parent.mkdir(parents=True, exist_ok=True)

        # Viewport randomisé pour éviter le fingerprinting
        width = 1366 + random.randint(-50, 50)
        height = 768 + random.randint(-30, 30)

        self._browser = await self._playwright.chromium.launch(
            headless=self.config.browser.headless,
            slow_mo=self.config.browser.slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        # Charger la session existante si disponible
        storage_state = str(session_path) if session_path.exists() else None

        stealth = Stealth(
            navigator_languages_override=("fr-FR", "fr"),
            navigator_platform_override="Linux x86_64",
        )

        self._context = await self._browser.new_context(
            storage_state=storage_state,
            viewport=ViewportSize(width=width, height=height),
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )

        await stealth.apply_stealth_async(self._context)
        self._page = await self._context.new_page()

        logger.info(
            "Navigateur lancé",
            session="restaurée" if storage_state else "nouvelle",
            viewport=f"{width}x{height}",
            max_minutes=self._max_session_minutes,
        )
        return self._page

    @property
    def session_expired(self) -> bool:
        """Vérifie si la durée maximale de session est atteinte."""
        if self._started_at is None:
            return False
        elapsed = (datetime.now(UTC) - self._started_at).total_seconds() / 60
        return elapsed >= self._max_session_minutes

    async def save_session(self) -> None:
        """Sauvegarde les cookies et le state du navigateur."""
        if self._context:
            session_path = SESSION_STATE_PATH
            await self._context.storage_state(path=str(session_path))
            logger.info("Session sauvegardée", path=str(session_path))

    async def close(self) -> None:
        """Ferme proprement le navigateur en sauvegardant la session."""
        try:
            await self.save_session()
        except Exception as e:
            logger.warning("Erreur sauvegarde session", error=str(e))
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Navigateur fermé")
