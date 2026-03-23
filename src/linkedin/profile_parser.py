"""LinkedIn profile information extraction from the page."""

from __future__ import annotations

import re

import structlog
from playwright.async_api import Page

logger = structlog.get_logger()


async def parse_profile(page: Page) -> dict[str, str | None]:
    """Extract key information from the currently displayed LinkedIn profile."""
    info: dict[str, str | None] = {
        "first_name": None,
        "last_name": None,
        "headline": None,
        "about": None,
        "company": None,
        "connection_degree": None,
        "pending_invitation": None,
    }

    try:
        # Full name
        name_el = page.locator("h1.text-heading-xlarge, h1.inline.t-24")
        if await name_el.count() > 0:
            full_name = (await name_el.first.text_content() or "").strip()
            parts = full_name.split(None, 1)
            if parts:
                info["first_name"] = parts[0]
                info["last_name"] = parts[1] if len(parts) > 1 else None

        # Headline (short summary below the name)
        headline_el = page.locator("div.text-body-medium.break-words, div.text-body-medium")
        if await headline_el.count() > 0:
            info["headline"] = (await headline_el.first.text_content() or "").strip() or None

        # About section
        about_el = page.locator(
            "div.inline-show-more-text--is-collapsed span[aria-hidden='true'], "
            "div.inline-show-more-text span[aria-hidden='true']"
        )
        if await about_el.count() > 0:
            info["about"] = (await about_el.first.text_content() or "").strip() or None

        # Current company (button in the top card)
        company_el = page.locator(
            "button[aria-label*='Entreprise actuelle'], button[aria-label*='Current company']"
        )
        if await company_el.count() > 0:
            info["company"] = (await company_el.first.text_content() or "").strip() or None

        # Connection degree
        degree_el = page.locator(
            "span.dist-value, "
            "span.text-body-small:has-text('1er'), "
            "span.text-body-small:has-text('2e'), "
            "span.text-body-small:has-text('3e')"
        )
        if await degree_el.count() > 0:
            degree_text = (await degree_el.first.text_content() or "").strip()
            # Extract just the degree (1er, 2e, 3e+)
            match = re.search(r"(1er|2e|3e\+?)", degree_text)
            if match:
                info["connection_degree"] = match.group(1)

        # Pending invitation
        pending_el = page.locator(
            "button:has-text('En attente'), "
            "button:has-text('Pending'), "
            "button[aria-label*='En attente'], "
            "button[aria-label*='Pending'], "
            "button:has-text('Retirer'), "
            "button:has-text('Withdraw')"
        )
        if await pending_el.count() > 0:
            info["pending_invitation"] = "true"

        logger.info(
            "Profil parsé",
            name=f"{info['first_name'] or ''} {info['last_name'] or ''}".strip(),
            degree=info["connection_degree"],
            pending=info["pending_invitation"] is not None,
        )

    except Exception as e:
        logger.error("Erreur parsing profil", error=str(e))

    return info
