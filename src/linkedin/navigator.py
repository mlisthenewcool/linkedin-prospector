"""LinkedIn profile navigation with human behavior simulation."""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.safety.human_behavior import human_scroll, random_mouse_move, simulate_reading

logger = structlog.get_logger()


async def check_for_restriction(page: Page) -> bool:
    """Detect LinkedIn restriction/checkpoint pages.

    Returns:
        True if a restriction is detected (navigation should stop).
    """
    url = page.url
    if any(pattern in url for pattern in ("/checkpoint/", "/checkpoint?", "/authwall")):
        logger.error("Page de restriction LinkedIn détectée", url=url)
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


class NavigationResult:
    """Result of navigating to a profile."""

    __slots__ = ("invalid_profile", "ok")

    def __init__(self, *, ok: bool, invalid_profile: bool = False) -> None:
        self.ok = ok
        self.invalid_profile = invalid_profile


NAV_OK = NavigationResult(ok=True)
NAV_TEMP_ERROR = NavigationResult(ok=False, invalid_profile=False)
NAV_INVALID = NavigationResult(ok=False, invalid_profile=True)


async def navigate_to_profile(
    page: Page, linkedin_url: str, *, light: bool = False
) -> NavigationResult:
    """Navigate to a LinkedIn profile with human behavior simulation.

    Args:
        light: If True, use shorter delays (for sync).

    Returns:
        NavigationResult with ok=True on success, invalid_profile=True if broken/deleted.
    """
    try:
        logger.debug("Navigation vers profil", url=linkedin_url)
        await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=20_000)

        if await check_for_restriction(page):
            return NAV_TEMP_ERROR

        if "/in/" not in page.url:
            logger.warning("Profil introuvable ou supprimé", url=linkedin_url, redirect=page.url)
            return NAV_INVALID

        # Adapted delays depending on mode
        read_time = (1.0, 2.0) if light else (2.0, 4.0)
        scroll_time = (0.5, 1.5) if light else (1.0, 3.0)
        end_time = (0.3, 0.8) if light else (0.5, 1.5)

        await simulate_reading(*read_time)
        await random_mouse_move(page)
        await human_scroll(page, "down")
        await simulate_reading(*scroll_time)
        await human_scroll(page, "up")
        await simulate_reading(*end_time)

        return NAV_OK

    except Exception as e:
        logger.error("Erreur navigation profil (temporaire)", url=linkedin_url, error=str(e))
        return NAV_TEMP_ERROR
