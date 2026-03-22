"""Navigation vers les profils LinkedIn avec simulation humaine."""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.config import Config
from src.safety.human_behavior import human_scroll, random_mouse_move, simulate_reading

logger = structlog.get_logger()


async def check_for_restriction(page: Page) -> bool:
    """Détecte les pages de restriction/checkpoint LinkedIn.

    Returns:
        True si une restriction est détectée (la navigation doit s'arrêter).
    """
    url = page.url
    if any(pattern in url for pattern in ("/checkpoint/", "/checkpoint?", "/authwall")):
        logger.error("Page de restriction LinkedIn détectée : %s", url)
        return True

    restriction_indicators = page.locator(
        "text='Your account has been restricted', "
        "text='Votre compte a été restreint', "
        "text='action limitée', "
        "text='temporarily restricted'"
    )
    if await restriction_indicators.count() > 0:
        logger.error("Restriction LinkedIn détectée sur la page")
        return True

    return False


async def navigate_to_profile(
    page: Page, linkedin_url: str, config: Config, *, light: bool = False
) -> bool:
    """Navigue vers un profil LinkedIn avec simulation humaine.

    Args:
        light: Si True, utilise des délais réduits (pour sync).
    """
    try:
        logger.info("Navigation vers : %s", linkedin_url)
        await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=20_000)

        if await check_for_restriction(page):
            return False

        if "/in/" not in page.url:
            logger.warning("URL inattendue après navigation : %s", page.url)
            return False

        # Délais adaptés selon le mode
        read_time = (1.0, 2.0) if light else (2.0, 4.0)
        scroll_time = (0.5, 1.5) if light else (1.0, 3.0)
        end_time = (0.3, 0.8) if light else (0.5, 1.5)

        await simulate_reading(*read_time)
        await random_mouse_move(page)
        await human_scroll(page, "down")
        await simulate_reading(*scroll_time)
        await human_scroll(page, "up")
        await simulate_reading(*end_time)

        return True

    except Exception as e:
        logger.error("Erreur navigation profil %s : %s", linkedin_url, e)
        return False


async def navigate_to_messaging(page: Page, config: Config) -> bool:
    """Navigue vers la messagerie LinkedIn."""
    try:
        await page.goto(
            f"{config.base_url}/messaging/",
            wait_until="domcontentloaded",
            timeout=15_000,
        )

        if await check_for_restriction(page):
            return False

        await simulate_reading(1.0, 2.0)
        return True
    except Exception as e:
        logger.error("Erreur navigation messagerie : %s", e)
        return False
