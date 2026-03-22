"""Orchestration des pipelines de prospection."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import replace

import structlog
import typer
from playwright.async_api import Page

from src.browser import BrowserManager
from src.config import Config
from src.database import Database
from src.linkedin.auth import is_session_valid
from src.linkedin.navigator import navigate_to_profile
from src.linkedin.profile_parser import parse_profile
from src.models import ActionType, Prospect, ProspectStatus
from src.safety.human_behavior import maybe_visit_feed, random_delay
from src.safety.rate_limiter import RateLimiter
from src.templates import TemplateEngine

logger = structlog.get_logger()

MAX_CONSECUTIVE_ERRORS = 3
BACKOFF_MIN_S = 60.0
BACKOFF_MAX_S = 180.0

ActionFn = Callable[
    [Page, Prospect, Database, Config, RateLimiter, TemplateEngine],
    Awaitable[bool],
]


async def start_browser_with_session(config: Config) -> tuple[BrowserManager, Page]:
    """Lance le navigateur et valide la session."""
    browser = BrowserManager(config)
    page = await browser.start()
    if not await is_session_valid(page, config):
        await browser.close()
        typer.echo("Session expirée — relancez 'login'", err=True)
        raise typer.Exit(1)
    return browser, page


async def enrich_prospect(
    page: Page,
    prospect: Prospect,
    db: Database,
) -> tuple[Prospect, dict[str, str | None]]:
    """Parse le profil LinkedIn et met à jour les infos en base.

    Retourne le prospect enrichi (nouveau frozen) et le dict d'infos brutes.
    """
    pid = prospect.require_id()
    info = await parse_profile(page)
    db.update_prospect_info(
        pid,
        first_name=info.get("first_name"),
        last_name=info.get("last_name"),
        headline=info.get("headline"),
        about=info.get("about"),
        company=info.get("company"),
        connection_degree=info.get("connection_degree"),
    )
    enriched = replace(
        prospect,
        first_name=info.get("first_name") or prospect.first_name,
        last_name=info.get("last_name") or prospect.last_name,
        company=info.get("company") or prospect.company,
    )
    return enriched, info


async def run_prospect_pipeline(
    config: Config,
    db: Database,
    prospects: list[Prospect],
    action_type: ActionType,
    action_fn: ActionFn,
    label: str,
    rate_limiter: RateLimiter,
) -> int:
    """Pipeline générique pour connect/message/followup.

    Gère : lancement navigateur, boucle sur prospects, enrichissement,
    rate limiting, backoff sur erreurs, bruit comportemental, durée de session.
    """
    browser, page = await start_browser_with_session(config)
    templates = TemplateEngine(config)

    try:
        typer.echo(f"\n{label} — {len(prospects)} prospect(s)...\n")

        sent = 0
        consecutive_errors = 0

        for i, prospect in enumerate(prospects, 1):
            try:
                prospect.require_id()
            except ValueError:
                logger.warning("Prospect sans ID ignoré", url=prospect.linkedin_url)
                continue

            if browser.session_expired:
                typer.echo("Durée de session max atteinte — arrêt de sécurité")
                break

            if not rate_limiter.can_perform(action_type):
                typer.echo(f"Limite atteinte après {sent}")
                break

            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                typer.echo("Trop d'erreurs consécutives — pause de sécurité")
                await asyncio.sleep(random.uniform(BACKOFF_MIN_S, BACKOFF_MAX_S))
                consecutive_errors = 0

            typer.echo(f"[{i}/{len(prospects)}] {prospect.display_name} — {prospect.linkedin_url}")

            success = False
            nav = await navigate_to_profile(page, prospect.linkedin_url)
            if nav.invalid_profile:
                pid = prospect.require_id()
                db.update_prospect_status(pid, ProspectStatus.INVALID_PROFILE)
                typer.echo("  profil invalide")
            elif nav.ok:
                prospect, _ = await enrich_prospect(page, prospect, db)
                if await action_fn(page, prospect, db, config, rate_limiter, templates):
                    sent += 1
                    success = True

            if success:
                consecutive_errors = 0
            else:
                consecutive_errors += 1

            if i < len(prospects):
                await random_delay(config)
                await maybe_visit_feed(page, config)

        typer.echo(f"\nTerminé : {sent}/{len(prospects)}")
        return sent

    finally:
        await browser.close()
