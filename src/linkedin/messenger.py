"""Envoi de messages et relances + détection de réponses."""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.config import Config
from src.database import Database
from src.linkedin.conversation import (
    open_message_dialog,
    scan_conversation,
    type_and_send_message,
)
from src.models import Action, ActionType, Prospect, ProspectStatus
from src.safety.rate_limiter import RateLimiter
from src.templates import TemplateEngine

logger = structlog.get_logger()


async def send_first_message(
    page: Page,
    prospect: Prospect,
    db: Database,
    config: Config,
    rate_limiter: RateLimiter,
    templates: TemplateEngine,
) -> bool:
    """Envoie le premier message de prospection à un prospect connecté."""
    pid = prospect.require_id()
    if not rate_limiter.can_perform(ActionType.MESSAGE):
        logger.warning("Rate limit atteint pour les messages")
        return False

    # Vérifier en base si on a déjà envoyé un message via l'outil
    if db.has_action(pid, ActionType.MESSAGE):
        logger.info("Message déjà envoyé — skip", prospect=prospect.display_name)
        db.update_prospect_status(pid, ProspectStatus.MESSAGED)
        return True

    try:
        if not await open_message_dialog(page, prospect):
            return False

        # Scanner la conversation pour détecter réponses et messages existants
        our_groups, prospect_replied = await scan_conversation(page, prospect, config)

        if prospect_replied:
            logger.info("Réponse détectée", prospect=prospect.display_name)
            db.update_prospect_status(pid, ProspectStatus.REPLIED)

            return True

        if our_groups > 0:
            logger.info("Message déjà envoyé — skip", prospect=prospect.display_name)
            db.update_prospect_status(pid, ProspectStatus.MESSAGED)

            return True

        message = templates.render_first_message(
            first_name=prospect.first_name or "Bonjour",
            company=prospect.company,
            headline=prospect.headline,
        )

        if not await type_and_send_message(page, message, config):
            return False

        db.log_action(
            Action(
                prospect_id=pid,
                action_type=ActionType.MESSAGE,
                message_sent=message,
                success=True,
            )
        )
        db.update_prospect_status(pid, ProspectStatus.MESSAGED)
        rate_limiter.record_action(ActionType.MESSAGE)

        logger.info("Message envoyé", prospect=prospect.display_name)
        return True

    except Exception as e:
        logger.error("Erreur envoi message", url=prospect.linkedin_url, error=str(e))
        db.log_action(
            Action(
                prospect_id=pid,
                action_type=ActionType.MESSAGE,
                success=False,
                error=str(e),
            )
        )
        return False


async def send_followup(
    page: Page,
    prospect: Prospect,
    db: Database,
    config: Config,
    rate_limiter: RateLimiter,
    templates: TemplateEngine,
) -> bool:
    """Envoie une relance à un prospect déjà messagé."""
    pid = prospect.require_id()
    if not rate_limiter.can_perform(ActionType.FOLLOWUP):
        logger.warning("Rate limit atteint pour les relances")
        return False

    try:
        if not await open_message_dialog(page, prospect):
            return False

        # Vérifier s'il a répondu entre-temps
        _our_groups, prospect_replied = await scan_conversation(page, prospect, config)

        if prospect_replied:
            logger.info("Réponse détectée", prospect=prospect.display_name)
            db.update_prospect_status(pid, ProspectStatus.REPLIED)

            return True

        message = templates.render_followup(
            first_name=prospect.first_name or "Bonjour",
        )

        if not await type_and_send_message(page, message, config):
            return False

        db.log_action(
            Action(
                prospect_id=pid,
                action_type=ActionType.FOLLOWUP,
                message_sent=message,
                success=True,
            )
        )
        db.update_prospect_status(pid, ProspectStatus.FOLLOWED_UP)
        rate_limiter.record_action(ActionType.FOLLOWUP)

        logger.info("Relance envoyée", prospect=prospect.display_name)
        return True

    except Exception as e:
        logger.error("Erreur relance", url=prospect.linkedin_url, error=str(e))
        db.log_action(
            Action(
                prospect_id=pid,
                action_type=ActionType.FOLLOWUP,
                success=False,
                error=str(e),
            )
        )
        return False
