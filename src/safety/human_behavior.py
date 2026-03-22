"""Simulation de comportement humain : délais, frappe, scroll, souris, bruit."""

from __future__ import annotations

import asyncio
import random

import structlog
from playwright.async_api import Page

from src.config import Config

logger = structlog.get_logger()


async def random_delay(config: Config) -> None:
    """Attend un délai aléatoire entre les actions."""
    delay = random.uniform(config.delays.min_delay, config.delays.max_delay)
    logger.debug("Délai aléatoire : %.1fs", delay)
    await asyncio.sleep(delay)


async def short_delay(min_s: float = 1.0, max_s: float = 3.0) -> None:
    """Petit délai entre sous-actions."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def human_type(page: Page, selector: str, text: str, config: Config) -> None:
    """Tape du texte caractère par caractère avec des délais humains."""
    element = page.locator(selector)
    await element.click()
    await short_delay(0.3, 0.8)

    for char in text:
        await element.press_sequentially(char, delay=0)
        delay_ms = random.randint(
            config.typing.min_char_delay_ms,
            config.typing.max_char_delay_ms,
        )
        await asyncio.sleep(delay_ms / 1000)

        # Pause plus longue de temps en temps (comme un humain qui réfléchit)
        if random.random() < 0.05:
            await asyncio.sleep(random.uniform(0.5, 1.5))


async def human_type_in_focused(page: Page, text: str, config: Config) -> None:
    """Tape du texte dans l'élément actuellement focus."""
    for char in text:
        await page.keyboard.type(char, delay=0)
        delay_ms = random.randint(
            config.typing.min_char_delay_ms,
            config.typing.max_char_delay_ms,
        )
        await asyncio.sleep(delay_ms / 1000)

        if random.random() < 0.05:
            await asyncio.sleep(random.uniform(0.5, 1.5))


async def human_scroll(page: Page, direction: str = "down") -> None:
    """Scroll naturel avec variation et parfois retour en arrière."""
    steps = random.randint(2, 5)

    for _ in range(steps):
        delta = random.randint(100, 400)
        if direction == "up":
            delta = -delta

        # Parfois un petit retour en arrière
        if random.random() < 0.15:
            await page.mouse.wheel(0, -random.randint(50, 150))
            await asyncio.sleep(random.uniform(0.3, 0.8))

        await page.mouse.wheel(0, delta)
        await asyncio.sleep(random.uniform(0.5, 1.5))


async def random_mouse_move(page: Page) -> None:
    """Déplace la souris aléatoirement pour simuler un humain."""
    x = random.randint(100, 1200)
    y = random.randint(100, 600)
    await page.mouse.move(x, y)
    await asyncio.sleep(random.uniform(0.1, 0.5))


async def simulate_reading(min_s: float = 2.0, max_s: float = 6.0) -> None:
    """Simule le temps de lecture d'une page."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def maybe_visit_feed(page: Page, config: Config, probability: float = 0.1) -> None:
    """Visite occasionnelle du feed pour simuler un comportement naturel."""
    if random.random() >= probability:
        return
    logger.debug("Bruit comportemental : visite du feed")
    try:
        await page.goto(
            f"{config.base_url}/feed/",
            wait_until="domcontentloaded",
            timeout=15_000,
        )
        await simulate_reading(3.0, 8.0)
        await human_scroll(page, "down")
        await simulate_reading(1.0, 3.0)
    except Exception as e:
        logger.debug("Erreur visite feed (bruit) : %s", e)
