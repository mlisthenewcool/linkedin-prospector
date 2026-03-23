"""CSV prospect importer into SQLite."""

from __future__ import annotations

import csv
from pathlib import Path

import structlog

from src.database import Database
from src.models import Prospect, ProspectStatus

logger = structlog.get_logger()

# Mapping of possible CSV column names to internal field names
COLUMN_MAP = {
    "linkedin_url": ["linkedin_url", "url", "profile_url", "linkedin", "profile"],
    "first_name": ["first_name", "firstname", "prenom", "prénom", "first"],
    "last_name": ["last_name", "lastname", "nom", "last"],
    "headline": ["headline", "titre", "title", "poste"],
    "company": ["company", "entreprise", "société", "societe", "organization"],
    "about": ["about", "infos", "description", "summary"],
    "status": ["status", "statut"],
    "connection_degree": ["connection_degree", "degree", "degré"],
}


def _normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_").replace("-", "_")


def _resolve_columns(headers: list[str]) -> dict[str, str | None]:
    """Resolve CSV column names to internal field names."""
    normalized = [_normalize_header(h) for h in headers]
    mapping: dict[str, str | None] = {}
    for field_name, aliases in COLUMN_MAP.items():
        mapping[field_name] = None
        for alias in aliases:
            if alias in normalized:
                mapping[field_name] = headers[normalized.index(alias)]
                break
    return mapping


def import_csv(db: Database, csv_path: Path) -> tuple[int, int]:
    """Import prospects from a CSV file. Returns (imported, skipped/duplicates)."""
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV vide ou sans en-têtes : {csv_path}")

        col_map = _resolve_columns(list(reader.fieldnames))
        url_col = col_map.get("linkedin_url")
        if not url_col:
            raise ValueError(
                f"Colonne URL LinkedIn introuvable. Colonnes trouvées : {reader.fieldnames}"
            )

        prospects_to_import: list[Prospect] = []
        for row in reader:
            url = row.get(url_col, "").strip()
            if not url or "linkedin.com" not in url:
                logger.warning("URL invalide ignorée", url=url)
                skipped += 1
                continue

            url = _normalize_linkedin_url(url)
            vals = {
                f: row.get(col_map.get(f) or "", "").strip() or None
                for f in (
                    "first_name",
                    "last_name",
                    "headline",
                    "company",
                    "about",
                    "connection_degree",
                    "status",
                )
            }

            try:
                status = ProspectStatus(vals["status"]) if vals["status"] else ProspectStatus.NEW
            except ValueError:
                status = ProspectStatus.NEW

            prospects_to_import.append(
                Prospect(
                    linkedin_url=url,
                    first_name=vals["first_name"],
                    last_name=vals["last_name"],
                    headline=vals["headline"],
                    company=vals["company"],
                    about=vals["about"],
                    connection_degree=vals["connection_degree"],
                    status=status,
                )
            )

    urls = [p.linkedin_url for p in prospects_to_import]
    unique_urls = set(urls)
    duplicates = len(urls) - len(unique_urls)
    if duplicates:
        logger.warning("URLs en double dans le CSV", count=duplicates)

    existing = {p.linkedin_url for p in db.get_all_prospects() if p.linkedin_url in unique_urls}
    new_count = len(unique_urls - existing)
    updated_count = len(unique_urls & existing)

    db.upsert_prospects_batch(prospects_to_import)

    if updated_count:
        logger.info("Prospects mis à jour", count=updated_count)
    logger.info("Import terminé", nouveaux=new_count)

    return new_count, skipped


def _normalize_linkedin_url(url: str) -> str:
    """Normalize a LinkedIn URL to a consistent format."""
    url = url.rstrip("/")
    # Strip tracking parameters
    if "?" in url:
        url = url.split("?")[0]
    # Ensure it's a full URL
    if not url.startswith("http"):
        url = "https://" + url
    return url
