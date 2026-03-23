"""Domain dataclasses: Prospect and Action."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class ProspectStatus(StrEnum):
    NEW = "new"
    CONNECTION_SENT = "connection_sent"
    CONNECTED = "connected"
    MESSAGED = "messaged"
    FOLLOWED_UP = "followed_up"
    REPLIED = "replied"
    INVALID_PROFILE = "invalid_profile"


class ActionType(StrEnum):
    INVITATION = "invitation"
    MESSAGE = "message"
    FOLLOWUP = "followup"


@dataclass(frozen=True, slots=True)
class Prospect:
    linkedin_url: str
    first_name: str | None = None
    last_name: str | None = None
    headline: str | None = None
    about: str | None = None
    company: str | None = None
    connection_degree: str | None = None
    status: ProspectStatus = ProspectStatus.NEW
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    synced_at: datetime | None = None

    def require_id(self) -> int:
        """Return the ID or raise ValueError if the prospect is not persisted."""
        if self.id is None:
            raise ValueError(f"Prospect sans ID : {self.linkedin_url}")
        return self.id

    @property
    def display_name(self) -> str:
        """Display name, falling back to URL if no name is available."""
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) if parts else self.linkedin_url


@dataclass(frozen=True, slots=True)
class Action:
    prospect_id: int
    action_type: ActionType
    message_sent: str | None = None
    success: bool = True
    error: str | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
