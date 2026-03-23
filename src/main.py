"""CLI principal : import, login, sync, connect, message, followup, export, list, status."""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import Annotated

import structlog
import typer

from src.browser import BrowserManager
from src.config import DB_PATH, LOG_PATH, Config, load_config
from src.csv_importer import import_csv
from src.database import Database
from src.linkedin.auth import manual_login
from src.linkedin.connection import send_connection_request
from src.linkedin.messenger import send_first_message, send_followup
from src.linkedin.navigator import navigate_to_profile
from src.linkedin.sync import sync_prospect
from src.models import ActionType, ProspectStatus
from src.safety.human_behavior import short_delay
from src.safety.rate_limiter import ACTION_LIMIT_MAP, RateLimiter
from src.workflow import enrich_prospect, run_prospect_pipeline, start_browser_with_session

logger = structlog.get_logger()

app = typer.Typer(
    help="Automatisation de prospection LinkedIn",
    add_completion=False,
    no_args_is_help=True,
)


# --- Helpers ---


def _config(ctx: typer.Context) -> Config:
    return ctx.ensure_object(Config)


def _resolve_status(status: str) -> ProspectStatus:
    """Convertit un string en ProspectStatus ou exit avec erreur."""
    try:
        return ProspectStatus(status)
    except ValueError:
        valid = ", ".join(s.value for s in ProspectStatus)
        typer.echo(f"Statut invalide : '{status}'. Valeurs possibles : {valid}", err=True)
        raise typer.Exit(1) from None


# --- Commandes ---


@app.command("import")
def cmd_import(
    csv_path: Annotated[Path, typer.Option("--csv", help="Chemin du CSV")],
) -> None:
    """Importer des prospects depuis un CSV."""
    with Database(DB_PATH) as db:
        imported, skipped = import_csv(db, csv_path)
        typer.echo(f"\nImport terminé : {imported} prospects importés, {skipped} ignorés")


@app.command()
def export(
    output: Annotated[Path, typer.Option("--output", "-o", help="Fichier de sortie")] = Path(
        "export.csv"
    ),
    status: Annotated[str | None, typer.Option(help="Filtrer par statut")] = None,
) -> None:
    """Exporter les prospects en CSV."""
    with Database(DB_PATH) as db:
        if status:
            prospects = db.get_prospects_by_status(_resolve_status(status))
        else:
            prospects = db.get_all_prospects()

        if not prospects:
            typer.echo("Aucun prospect à exporter")
            return

        fields = [
            "linkedin_url",
            "first_name",
            "last_name",
            "headline",
            "about",
            "company",
            "connection_degree",
            "status",
            "synced_at",
            "created_at",
            "updated_at",
        ]
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for p in prospects:
                writer.writerow(
                    {
                        "linkedin_url": p.linkedin_url,
                        "first_name": p.first_name or "",
                        "last_name": p.last_name or "",
                        "headline": p.headline or "",
                        "about": p.about or "",
                        "company": p.company or "",
                        "connection_degree": p.connection_degree or "",
                        "status": p.status.value,
                        "synced_at": p.synced_at.isoformat() if p.synced_at else "",
                        "created_at": p.created_at.isoformat(),
                        "updated_at": p.updated_at.isoformat(),
                    }
                )

        typer.echo(f"{len(prospects)} prospects exportés → {output}")


@app.command()
def login(ctx: typer.Context) -> None:
    """Login manuel sur LinkedIn."""
    config = _config(ctx)

    async def _run() -> None:
        browser = BrowserManager(config)
        try:
            page = await browser.start()
            success = await manual_login(page, config)
            if success:
                await browser.save_session()
                typer.echo("\nLogin réussi — session sauvegardée")
            else:
                typer.echo("\nLogin échoué", err=True)
                raise typer.Exit(1)
        finally:
            await browser.close()

    asyncio.run(_run())


@app.command()
def sync(
    ctx: typer.Context,
    limit: Annotated[int | None, typer.Option(help="Nombre max de profils")] = None,
    status: Annotated[str | None, typer.Option(help="Filtrer par statut")] = None,
    all_prospects: Annotated[
        bool, typer.Option("--all", help="Re-sync tous les prospects")
    ] = False,
) -> None:
    """Synchroniser les statuts avec l'état réel LinkedIn."""
    config = _config(ctx)

    with Database(DB_PATH) as db:
        if status:
            resolved = _resolve_status(status)
            prospects = db.get_prospects_by_status(resolved, limit=limit)
        elif all_prospects:
            prospects = db.get_all_prospects()[:limit] if limit else db.get_all_prospects()
        else:
            prospects = db.get_unsynced_prospects(limit=limit)

        if not prospects:
            typer.echo("Aucun prospect à synchroniser")
            return

        async def _run() -> None:
            browser, page = await start_browser_with_session(config)
            try:
                typer.echo(f"\nSynchronisation de {len(prospects)} prospects...\n")

                changes: dict[str, int] = {}
                unchanged = 0

                for i, prospect in enumerate(prospects, 1):
                    try:
                        pid = prospect.require_id()
                    except ValueError:
                        logger.warning("Prospect sans ID ignoré", url=prospect.linkedin_url)
                        continue

                    if browser.session_expired:
                        typer.echo("Durée de session max atteinte — arrêt de sécurité")
                        break

                    typer.echo(
                        f"[{i}/{len(prospects)}] {prospect.display_name} ({prospect.status.value})",
                        nl=False,
                    )

                    nav = await navigate_to_profile(page, prospect.linkedin_url, light=True)
                    if nav.invalid_profile:
                        db.update_prospect_status(pid, ProspectStatus.INVALID_PROFILE)
                        db.mark_synced(pid)
                        typer.echo(" → invalid_profile")
                        changes["invalid_profile"] = changes.get("invalid_profile", 0) + 1
                        continue
                    if not nav.ok:
                        typer.echo(" — erreur navigation (temporaire)")
                        continue

                    prospect, info = await enrich_prospect(page, prospect, db)
                    new_status = await sync_prospect(page, prospect, db, config, info)
                    db.mark_synced(pid)

                    if new_status:
                        typer.echo(f" → {new_status}")
                        changes[new_status] = changes.get(new_status, 0) + 1
                    else:
                        typer.echo(" — inchangé")
                        unchanged += 1

                    if i < len(prospects):
                        await short_delay(3.0, 8.0)

                typer.echo("\nSynchronisation terminée :")
                typer.echo(f"  Inchangés    : {unchanged}")
                for s, count in changes.items():
                    if count:
                        typer.echo(f"  → {s:<13}: {count}")

            finally:
                await browser.close()

        asyncio.run(_run())


@app.command()
def connect(
    ctx: typer.Context,
    limit: Annotated[int | None, typer.Option(help="Nombre max d'invitations")] = None,
) -> None:
    """Envoyer des invitations aux prospects 'new'."""
    config = _config(ctx)

    with Database(DB_PATH) as db:
        rate_limiter = RateLimiter(db, config)
        remaining = rate_limiter.remaining(ActionType.INVITATION)
        effective_limit = min(limit or remaining, remaining)

        prospects = db.get_prospects_by_status(ProspectStatus.NEW, limit=effective_limit)
        if not prospects:
            typer.echo("Aucun prospect 'new' à contacter")
            return

        asyncio.run(
            run_prospect_pipeline(
                config,
                db,
                prospects,
                ActionType.INVITATION,
                send_connection_request,
                f"Envoi d'invitations (limite: {effective_limit})",
                rate_limiter,
            )
        )


@app.command()
def message(
    ctx: typer.Context,
    limit: Annotated[int | None, typer.Option(help="Nombre max de messages")] = None,
) -> None:
    """Envoyer les premiers messages aux prospects 'connected'."""
    config = _config(ctx)

    with Database(DB_PATH) as db:
        rate_limiter = RateLimiter(db, config)
        remaining = rate_limiter.remaining(ActionType.MESSAGE)
        effective_limit = min(limit or remaining, remaining)

        prospects = db.get_prospects_by_status(ProspectStatus.CONNECTED, limit=effective_limit)
        if not prospects:
            typer.echo("Aucun prospect 'connected' à qui envoyer un message")
            return

        asyncio.run(
            run_prospect_pipeline(
                config,
                db,
                prospects,
                ActionType.MESSAGE,
                send_first_message,
                "Envoi de messages",
                rate_limiter,
            )
        )


@app.command()
def followup(
    ctx: typer.Context,
    limit: Annotated[int | None, typer.Option(help="Nombre max de relances")] = None,
) -> None:
    """Envoyer des relances aux prospects 'messaged' sans réponse."""
    config = _config(ctx)

    with Database(DB_PATH) as db:
        rate_limiter = RateLimiter(db, config)
        remaining = rate_limiter.remaining(ActionType.FOLLOWUP)
        effective_limit = min(limit or remaining, remaining)

        prospects = db.get_messaged_prospects_for_followup(
            config.delays.followup_after_days, limit=effective_limit
        )
        if not prospects:
            typer.echo("Aucun prospect éligible à une relance")
            return

        asyncio.run(
            run_prospect_pipeline(
                config,
                db,
                prospects,
                ActionType.FOLLOWUP,
                send_followup,
                "Envoi de relances",
                rate_limiter,
            )
        )


@app.command("list")
def cmd_list(
    status: Annotated[str | None, typer.Option(help="Filtrer par statut")] = None,
    limit: Annotated[int, typer.Option(help="Nombre max à afficher")] = 20,
) -> None:
    """Lister les prospects."""
    with Database(DB_PATH) as db:
        if status:
            prospects = db.get_prospects_by_status(_resolve_status(status), limit=limit)
        else:
            prospects = db.get_all_prospects()[:limit]

        if not prospects:
            typer.echo("Aucun prospect trouvé")
            return

        for p in prospects:
            typer.echo(f"\n{'─' * 60}")
            typer.echo(f"  {p.display_name}  [{p.status.value}]  {p.connection_degree or ''}")
            typer.echo(f"  {p.linkedin_url}")
            if p.headline:
                typer.echo(f"  Headline : {p.headline}")
            if p.company:
                typer.echo(f"  Entreprise : {p.company}")
            if p.about:
                preview = p.about[:150] + "..." if len(p.about) > 150 else p.about
                typer.echo(f"  Infos : {preview}")
        typer.echo(f"\n{'─' * 60}")
        typer.echo(f"  {len(prospects)} prospect(s) affiché(s)\n")


@app.command()
def status(ctx: typer.Context) -> None:
    """Afficher les statistiques."""
    config = _config(ctx)
    with Database(DB_PATH) as db:
        counts = db.count_by_status()
        total = sum(counts.values())

        typer.echo("\n" + "=" * 45)
        typer.echo("  STATISTIQUES PROSPECTION")
        typer.echo("=" * 45)
        typer.echo(f"  Total prospects     : {total}")
        typer.echo("  ─────────────────────────────")
        for s in ProspectStatus:
            count = counts.get(s.value, 0)
            bar = "█" * min(count, 30)
            typer.echo(f"  {s.value:<20}: {count:>4}  {bar}")
        typer.echo("  ─────────────────────────────")

        typer.echo("\n  Aujourd'hui :")
        for action_type, limit_attr in ACTION_LIMIT_MAP.items():
            current = db.get_daily_count(action_type)
            daily_limit = getattr(config.limits, limit_attr)
            typer.echo(f"    {action_type.value:<12}: {current}/{daily_limit}")

        typer.echo("=" * 45 + "\n")


# --- Entrypoint ---


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    log_file = open(LOG_PATH, "a", encoding="utf-8")  # noqa: SIM115

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        logger_factory=structlog.WriteLoggerFactory(file=log_file),
        cache_logger_on_first_use=True,
    )


@app.callback()
def callback(
    ctx: typer.Context,
    config: Annotated[Path | None, typer.Option(help="Chemin du fichier config.toml")] = None,
) -> None:
    """Automatisation de prospection LinkedIn."""
    loaded = load_config(config) if config else load_config()
    setup_logging()
    ctx.obj = loaded


if __name__ == "__main__":
    app()
