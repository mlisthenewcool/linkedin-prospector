"""Synchronisation des statuts prospects avec l'état réel LinkedIn.

Approche hybride :
  - La DB est la source de vérité pour les actions faites via l'outil.
  - Le scan de conversation (li.msg-s-message-list__event) détecte les messages
    manuels et les réponses du prospect, en filtrant les notifications système.

Logique :
  (1) Pas dans le réseau (pas 1er degré) :
      - Invitation en attente détectée     → CONNECTION_SENT
      - Sinon                              → NEW
  (2) Dans le réseau (1er degré) :
      - Réponse du prospect détectée       → REPLIED
      - On a messagé (DB ou conversation)  → MESSAGED / FOLLOWED_UP
      - Rien                               → CONNECTED
"""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.config import Config
from src.database import Database
from src.linkedin.conversation import (
    close_message_dialog,
    open_message_dialog,
    scan_conversation,
)
from src.models import ActionType, Prospect, ProspectStatus

logger = structlog.get_logger()


async def sync_prospect(
    page: Page,
    prospect: Prospect,
    db: Database,
    config: Config,
    info: dict[str, str | None],
) -> str | None:
    """Détermine le vrai statut LinkedIn et met à jour la base.

    Returns:
        Le nouveau statut si changé, None si inchangé.
    """
    pid = prospect.require_id()
    connection = info.get("connection_degree") or ""

    # (1) Pas dans le réseau
    if connection != "1er":
        pending = info.get("pending_invitation") is not None
        if pending:
            if prospect.status != ProspectStatus.CONNECTION_SENT:
                db.update_prospect_status(pid, ProspectStatus.CONNECTION_SENT)
                return ProspectStatus.CONNECTION_SENT.value
        elif prospect.status != ProspectStatus.NEW:
            db.update_prospect_status(pid, ProspectStatus.NEW)
            return ProspectStatus.NEW.value
        return None

    # (2) Dans le réseau — vérifier DB puis conversation

    # Ce qu'on sait via la DB (actions de l'outil)
    has_message = db.has_action(pid, ActionType.MESSAGE)
    has_followup = db.has_action(pid, ActionType.FOLLOWUP)

    # Scanner la conversation LinkedIn pour détecter réponses + messages manuels
    our_groups = 0
    prospect_replied = False
    if await open_message_dialog(page, prospect):
        our_groups, prospect_replied = await scan_conversation(page, prospect, config)
        await close_message_dialog()

    # Déterminer si on a messagé (outil OU manuellement)
    we_messaged = has_message or has_followup
    if not we_messaged and our_groups > 0:
        we_messaged = True
        logger.info(
            "Message manuel détecté",
            prospect=prospect.display_name,
            groups=our_groups,
        )

    # Résoudre le statut
    if prospect_replied:
        new_status = ProspectStatus.REPLIED
    elif has_followup:
        new_status = ProspectStatus.FOLLOWED_UP
    elif we_messaged:
        new_status = ProspectStatus.MESSAGED
    else:
        new_status = ProspectStatus.CONNECTED

    if new_status != prospect.status:
        db.update_prospect_status(pid, new_status)
        return new_status.value

    return None
