"""Prospect status synchronization with actual LinkedIn state.

Hybrid approach:
  - The DB is the source of truth for actions performed via the tool.
  - Conversation scanning (li.msg-s-message-list__event) detects manual
    messages and prospect replies, filtering out system notifications.

Logic:
  (1) Not in network (not 1st degree):
      - Pending invitation detected       → CONNECTION_SENT
      - Otherwise                          → NEW
  (2) In network (1st degree):
      - Prospect reply detected            → REPLIED
      - We messaged (DB or conversation)   → MESSAGED / FOLLOWED_UP
      - Nothing                            → CONNECTED
"""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.config import Config
from src.database import Database
from src.linkedin.conversation import (
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
    """Determine the real LinkedIn status and update the database.

    Returns:
        The new status if changed, None if unchanged.
    """
    pid = prospect.require_id()
    connection = info.get("connection_degree") or ""

    # (1) Not in network
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

    # (2) In network — check DB then conversation

    # What we know from DB (tool actions)
    has_message = db.has_action(pid, ActionType.MESSAGE)
    has_followup = db.has_action(pid, ActionType.FOLLOWUP)

    # Scan LinkedIn conversation to detect replies + manual messages
    our_groups = 0
    prospect_replied = False
    if await open_message_dialog(page, prospect):
        our_groups, prospect_replied = await scan_conversation(page, prospect, config)

    # Determine if we messaged (tool OR manually)
    we_messaged = has_message or has_followup
    if not we_messaged and our_groups > 0:
        we_messaged = True
        logger.info(
            "Message manuel détecté",
            prospect=prospect.display_name,
            groups=our_groups,
        )

    # Resolve status
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
