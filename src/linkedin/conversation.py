"""LinkedIn conversation management: opening, scanning, sending."""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.config import Config
from src.models import Prospect
from src.safety.human_behavior import human_type_in_focused, short_delay, simulate_reading

logger = structlog.get_logger()


async def _extract_profile_urn(page: Page) -> str | None:
    """Extract the prospect's URN (ACoAA...) from the LinkedIn profile page."""
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
    """Open the conversation with the prospect on the messaging page.

    Extracts the profile URN from the current page (must be on the profile),
    then navigates to /messaging/thread/new/?recipient=<URN> to ensure
    the correct conversation is opened.
    """
    urn = await _extract_profile_urn(page)
    if not urn:
        logger.warning("URN introuvable", url=prospect.linkedin_url)
        return False

    url = f"https://www.linkedin.com/messaging/thread/new/?recipient={urn}"
    logger.debug("Ouverture conversation", prospect=prospect.display_name)
    await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
    await short_delay(2.0, 4.0)

    # Check that the text input area is available
    msg_box = page.locator(
        "div[role='textbox'][contenteditable='true'], div.msg-form__contenteditable"
    ).first
    if await msg_box.count() == 0:
        logger.warning("Zone de message non trouvée", url=prospect.linkedin_url)
        return False

    return True


async def type_and_send_message(page: Page, message: str, config: Config) -> bool:
    """Type a message character by character and send it."""
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

    # Fallback: Enter
    await page.keyboard.press("Enter")
    await simulate_reading(1.0, 2.0)
    return True


async def scan_conversation(page: Page, prospect: Prospect, config: Config) -> tuple[int, bool]:
    """Scan the messages in the open conversation.

    Iterates over ``li.msg-s-message-list__event`` and only keeps those
    containing a ``span.msg-s-message-group__name`` (= actual messages),
    ignoring system notifications ("You are now connected").

    Returns:
        (our_message_groups, prospect_replied)
    """
    user_name = config.user.first_name.lower()
    prospect_name = (prospect.first_name or "").lower()

    groups = page.locator("li.msg-s-message-list__event")
    group_count = await groups.count()

    our_groups = 0
    prospect_replied = False

    for idx in range(group_count):
        event = groups.nth(idx)
        sender_el = event.locator("span.msg-s-message-group__name").first
        if await sender_el.count() == 0:
            continue  # System notification or non-message element

        sender = (await sender_el.text_content() or "").strip().lower()
        logger.debug("Événement conversation", index=idx + 1, sender=sender)

        if user_name and (user_name in sender or sender in ("vous", "you")):
            our_groups += 1
        elif prospect_name and prospect_name in sender:
            prospect_replied = True

    logger.info(
        "Conversation scannée",
        prospect=prospect.display_name,
        events=group_count,
        our_messages=our_groups,
        replied=prospect_replied,
    )

    return our_groups, prospect_replied
