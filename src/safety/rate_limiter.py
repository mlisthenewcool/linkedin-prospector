"""Daily rate limiting via database counters."""

from __future__ import annotations

import structlog

from src.config import Config
from src.database import Database
from src.models import ActionType

logger = structlog.get_logger()

ACTION_LIMIT_MAP = {
    ActionType.INVITATION: "invitations_per_day",
    ActionType.MESSAGE: "messages_per_day",
    ActionType.FOLLOWUP: "followups_per_day",
}


class RateLimiter:
    def __init__(self, db: Database, config: Config) -> None:
        self.db = db
        self.config = config
        self.session_action_count = 0
        self._daily_counts: dict[ActionType, int] = {}

    def _get_daily_count(self, action_type: ActionType) -> int:
        """Return the daily counter, with in-memory cache."""
        if action_type not in self._daily_counts:
            self._daily_counts[action_type] = self.db.get_daily_count(action_type)
        return self._daily_counts[action_type]

    def can_perform(self, action_type: ActionType) -> bool:
        """Check whether the action is allowed (daily + session limits)."""
        if self.session_action_count >= self.config.limits.actions_per_session:
            logger.warning(
                "Limite session atteinte",
                current=self.session_action_count,
                limit=self.config.limits.actions_per_session,
            )
            return False

        limit_attr = ACTION_LIMIT_MAP.get(action_type)
        if limit_attr:
            daily_limit = getattr(self.config.limits, limit_attr)
            current_count = self._get_daily_count(action_type)
            if current_count >= daily_limit:
                logger.warning(
                    "Limite journalière atteinte",
                    action=action_type.value,
                    current=current_count,
                    limit=daily_limit,
                )
                return False

        return True

    def record_action(self, action_type: ActionType) -> None:
        """Record a performed action."""
        new_count = self.db.increment_daily_counter(action_type)
        self._daily_counts[action_type] = new_count
        self.session_action_count += 1

    def remaining(self, action_type: ActionType) -> int:
        """Number of remaining actions of this type for today."""
        limit_attr = ACTION_LIMIT_MAP.get(action_type)
        if not limit_attr:
            return 999
        daily_limit = getattr(self.config.limits, limit_attr)
        current = self._get_daily_count(action_type)
        session_remaining = self.config.limits.actions_per_session - self.session_action_count
        return min(daily_limit - current, session_remaining)
