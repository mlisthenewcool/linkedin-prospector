"""Envoi de demandes de connexion LinkedIn (sans note)."""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.config import Config
from src.database import Database
from src.models import Action, ActionType, Prospect, ProspectStatus
from src.safety.human_behavior import short_delay, simulate_reading
from src.safety.rate_limiter import RateLimiter
from src.templates import TemplateEngine

logger = structlog.get_logger()


async def send_connection_request(
    page: Page,
    prospect: Prospect,
    db: Database,
    _config: Config,
    rate_limiter: RateLimiter,
    _templates: TemplateEngine,
) -> bool:
    """Envoie une demande de connexion sans note à un prospect."""
    pid = prospect.require_id()
    if not rate_limiter.can_perform(ActionType.INVITATION):
        logger.warning("Rate limit atteint pour les invitations")
        return False

    try:
        # Chercher le bouton "Se connecter" / "Connect"
        connect_btn = page.locator(
            "button:has-text('Se connecter'), "
            "button:has-text('Connect'), "
            "button[aria-label*='Inviter'], "
            "button[aria-label*='Connect']"
        ).first

        if await connect_btn.count() == 0:
            # Peut-être dans le menu "Plus" / "More"
            more_btn = page.locator(
                "button:has-text('Plus'), button:has-text('More'), button[aria-label*='Plus d']"
            ).first
            if await more_btn.count() > 0:
                await more_btn.click()
                await short_delay(0.5, 1.5)
                connect_btn = page.locator(
                    "span:has-text('Se connecter'), span:has-text('Connect')"
                ).first

        if await connect_btn.count() == 0:
            logger.info(
                "Bouton connexion absent — peut-être déjà connecté",
                url=prospect.linkedin_url,
            )
            db.update_prospect_status(pid, ProspectStatus.CONNECTED)
            return True

        await connect_btn.click()
        await short_delay(1.0, 2.0)

        # Envoyer directement sans note — cliquer "Envoyer" si modal apparaît
        send_btn = page.locator(
            "button:has-text('Envoyer'), button:has-text('Send'), "
            "button[aria-label*='Envoyer'], button[aria-label*='Send now']"
        ).first

        if await send_btn.count() > 0:
            await send_btn.click()
            await simulate_reading(1.0, 2.0)

            db.log_action(
                Action(
                    prospect_id=pid,
                    action_type=ActionType.INVITATION,
                    success=True,
                )
            )
            db.update_prospect_status(pid, ProspectStatus.CONNECTION_SENT)
            rate_limiter.record_action(ActionType.INVITATION)

            logger.info("Invitation envoyée", prospect=prospect.display_name)
            return True

        logger.warning("Bouton Envoyer non trouvé", url=prospect.linkedin_url)
        return False

    except Exception as e:
        logger.error("Erreur envoi invitation", url=prospect.linkedin_url, error=str(e))
        db.log_action(
            Action(
                prospect_id=pid,
                action_type=ActionType.INVITATION,
                success=False,
                error=str(e),
            )
        )
        return False
