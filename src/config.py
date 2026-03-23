"""Chargement de la configuration TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.toml"

# Chemins fixes (pas besoin de les configurer)
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "prospector.db"
SESSION_STATE_PATH = DATA_DIR / "session" / "state.json"
LOG_PATH = PROJECT_ROOT / "logs" / "prospector.log"
TEMPLATES_DIR = PROJECT_ROOT / "config" / "templates"


@dataclass(frozen=True)
class LimitsConfig:
    invitations_per_day: int
    messages_per_day: int
    followups_per_day: int
    actions_per_session: int


@dataclass(frozen=True)
class DelaysConfig:
    min_delay: int
    max_delay: int
    followup_after_days: int


@dataclass(frozen=True)
class TypingConfig:
    min_char_delay_ms: int
    max_char_delay_ms: int


@dataclass(frozen=True)
class BrowserConfig:
    headless: bool
    slow_mo: int


@dataclass(frozen=True)
class UserConfig:
    first_name: str
    last_name: str
    title: str


@dataclass(frozen=True)
class Config:
    base_url: str
    limits: LimitsConfig
    delays: DelaysConfig
    typing: TypingConfig
    browser: BrowserConfig
    user: UserConfig


LINKEDIN_USER_FILE = PROJECT_ROOT / "config" / "linkedin_user.toml"


def _load_user_config(raw: dict[str, Any]) -> UserConfig:
    """Charge le user config : config.toml > linkedin_user.toml auto-détecté."""
    auto: dict[str, str] = {}
    if LINKEDIN_USER_FILE.exists():
        with open(LINKEDIN_USER_FILE, "rb") as f:
            auto = tomllib.load(f)

    user_raw = raw.get("user", {})
    return UserConfig(
        first_name=user_raw.get("first_name") or auto.get("first_name", ""),
        last_name=user_raw.get("last_name") or auto.get("last_name", ""),
        title=user_raw.get("title") or auto.get("title", ""),
    )


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    """Charge la configuration depuis un fichier TOML."""
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    return Config(
        base_url=raw["linkedin"]["base_url"],
        limits=LimitsConfig(**raw["limits"]),
        delays=DelaysConfig(**raw["delays"]),
        typing=TypingConfig(**raw["typing"]),
        browser=BrowserConfig(**raw["browser"]),
        user=_load_user_config(raw),
    )
