"""Gestion des conversations LinkedIn : ouverture, scan, envoi."""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.config import Config
from src.models import Prospect
from src.safety.human_behavior import human_type_in_focused, short_delay, simulate_reading

logger = structlog.get_logger()


async def _extract_profile_urn(page: Page) -> str | None:
    """Extrait l'URN (ACoAA...) du prospect depuis la page de profil LinkedIn."""
    return await page.evaluate(
        """() => {
        const links = document.querySelectorAll('a[href*="ACoAA"]');
        for (const link of links) {
            const match = link.href.match(/(ACoAA[A-Za-z0-9_-]+)/);
            if (match) return match[1];
        }
        const main = document.querySelector('main') || document.body;
        const match = main.innerHTML.match(/(ACoAA[A-Za-z0-9_-]+)/);
        return match ? match[1] : null;
    }"""
    )


async def open_message_dialog(page: Page, prospect: Prospect) -> bool:
    """Ouvre la conversation avec le prospect sur la page de messagerie.

    Extrait l'URN du profil depuis la page actuelle (doit être sur le profil),
    puis navigue vers /messaging/thread/new/?recipient=<URN> pour garantir
    l'ouverture de la bonne conversation.
    """
    urn = await _extract_profile_urn(page)
    if not urn:
        logger.warning("URN introuvable pour %s", prospect.linkedin_url)
        return False

    url = f"https://www.linkedin.com/messaging/thread/new/?recipient={urn}"
    logger.info("Navigation vers la conversation : %s", prospect.first_name)
    await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
    await short_delay(2.0, 4.0)

    # Vérifier que la zone de texte est disponible
    msg_box = page.locator(
        "div[role='textbox'][contenteditable='true'], div.msg-form__contenteditable"
    ).first
    if await msg_box.count() == 0:
        logger.warning("Zone de message non trouvée pour %s", prospect.linkedin_url)
        return False

    return True


async def close_message_dialog(page: Page) -> None:
    """No-op — sur la page de messagerie, pas d'overlay à fermer.

    On naviguera vers le prochain profil directement.
    """


async def type_and_send_message(page: Page, message: str, config: Config) -> bool:
    """Tape un message caractère par caractère et l'envoie."""
    msg_box = page.locator(
        "div[role='textbox'][contenteditable='true'], div.msg-form__contenteditable"
    ).first

    await msg_box.click()
    await short_delay(0.3, 0.8)

    await human_type_in_focused(page, message, config)
    await short_delay(0.5, 1.5)

    send_btn = page.locator(
        "button.msg-form__send-button, "
        "button:has-text('Envoyer'), "
        "button:has-text('Send'), "
        "button[type='submit']"
    ).first

    if await send_btn.count() > 0 and await send_btn.is_enabled():
        await send_btn.click()
        await simulate_reading(1.0, 2.0)
        return True

    # Fallback : Enter
    await page.keyboard.press("Enter")
    await simulate_reading(1.0, 2.0)
    return True


async def scan_conversation(page: Page, prospect: Prospect, config: Config) -> tuple[int, bool]:
    """Scanne les messages de la conversation ouverte.

    Itère sur les ``li.msg-s-message-list__event`` et ne retient que ceux
    qui contiennent un ``span.msg-s-message-group__name`` (= vrais messages),
    ignorant les notifications système (« Vous êtes maintenant en contact »).

    Returns:
        (our_message_groups, prospect_replied)
    """
    user_name = (config.user.first_name or "").lower()
    prospect_name = (prospect.first_name or "").lower()

    groups = page.locator("li.msg-s-message-list__event")
    group_count = await groups.count()

    our_groups = 0
    prospect_replied = False

    for idx in range(group_count):
        event = groups.nth(idx)
        sender_el = event.locator("span.msg-s-message-group__name").first
        if await sender_el.count() == 0:
            continue  # Notification système ou élément non-message

        sender = (await sender_el.text_content() or "").strip().lower()
        logger.debug("  événement %d — expéditeur: '%s'", idx + 1, sender)

        if user_name and (user_name in sender or sender in ("vous", "you")):
            our_groups += 1
        elif prospect_name and prospect_name in sender:
            prospect_replied = True

    logger.info(
        "Conversation avec %s : %d événement(s), nous=%d, réponse=%s",
        prospect.first_name,
        group_count,
        our_groups,
        prospect_replied,
    )

    return our_groups, prospect_replied
