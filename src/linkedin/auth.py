"""Login manuel, validation de session LinkedIn, et sauvegarde du profil utilisateur."""

from __future__ import annotations

import asyncio

import structlog
from playwright.async_api import Page

from src.config import LINKEDIN_USER_FILE, Config

logger = structlog.get_logger()

FEED_URL = "https://www.linkedin.com/feed/"
LOGIN_URL = "https://www.linkedin.com/login"


def _escape_toml_string(s: str) -> str:
    """Échappe une valeur pour inclusion dans un string TOML entre guillemets."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def save_linkedin_user(first_name: str, last_name: str, title: str) -> None:
    """Sauvegarde les infos user détectées depuis LinkedIn."""
    LINKEDIN_USER_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"# Auto-détecté depuis LinkedIn — ne pas modifier manuellement\n"
        f'first_name = "{_escape_toml_string(first_name)}"\n'
        f'last_name = "{_escape_toml_string(last_name)}"\n'
        f'title = "{_escape_toml_string(title)}"\n'
    )
    LINKEDIN_USER_FILE.write_text(content, encoding="utf-8")


async def manual_login(page: Page, config: Config) -> bool:
    """Ouvre LinkedIn pour un login manuel. Attend que l'utilisateur se connecte."""
    logger.info("Ouverture de LinkedIn pour login manuel...")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")

    print("\n" + "=" * 60)
    print("  CONNEXION MANUELLE REQUISE")
    print("  Connectez-vous dans le navigateur qui vient de s'ouvrir.")
    print("  (Gérez le CAPTCHA si nécessaire)")
    print("=" * 60 + "\n")

    try:
        await page.wait_for_url("**/feed/**", timeout=300_000)
        logger.info("Login réussi — feed LinkedIn détecté")
        return True
    except Exception:
        logger.error("Timeout — login non complété en 5 minutes")
        return False


async def _detect_linkedin_user(page: Page) -> None:
    """Détecte le nom et titre du user connecté depuis le feed LinkedIn."""
    try:
        nav_photo = page.locator(
            "img.global-nav__me-photo, button[class*='global-nav__primary-link'] img"
        )
        if await nav_photo.count() > 0:
            alt = (await nav_photo.first.get_attribute("alt") or "").strip()
            if alt:
                parts = alt.split(None, 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""

                title = ""
                title_el = page.locator("div.profile-card p").first
                if await title_el.count() > 0:
                    title = (await title_el.text_content() or "").strip()

                save_linkedin_user(first_name, last_name, title)
                logger.info("User LinkedIn détecté : %s %s — %s", first_name, last_name, title)
    except Exception as e:
        logger.debug("Détection user LinkedIn échouée : %s", e)


async def is_session_valid(page: Page, config: Config) -> bool:
    """Vérifie si la session sauvegardée est encore valide."""
    try:
        await page.goto(FEED_URL, wait_until="domcontentloaded", timeout=15_000)
        await asyncio.sleep(2)

        current_url = page.url
        if "/login" in current_url or "/checkpoint" in current_url:
            logger.warning("Session expirée — redirection vers login")
            return False

        feed = page.locator("div.feed-shared-update-v2, div.scaffold-layout__main")
        if await feed.count() > 0:
            logger.info("Session valide")
            await _detect_linkedin_user(page)
            return True

        if "/feed" in current_url:
            logger.info("Session probablement valide (URL feed)")
            await _detect_linkedin_user(page)
            return True

        logger.warning("Session douteuse — état inconnu")
        return False

    except Exception as e:
        logger.error("Erreur validation session : %s", e)
        return False
