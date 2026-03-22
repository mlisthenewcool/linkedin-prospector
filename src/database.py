"""Schema SQLite, CRUD et compteurs journaliers."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from types import TracebackType

from src.models import Action, ActionType, Prospect, ProspectStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    linkedin_url TEXT UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    headline TEXT,
    about TEXT,
    company TEXT,
    connection_degree TEXT,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    message_sent TEXT,
    success INTEGER DEFAULT 1,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prospect_id) REFERENCES prospects(id)
);

CREATE TABLE IF NOT EXISTS daily_counters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    action_type TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    UNIQUE(day, action_type)
);
"""


_UPSERT_PROSPECT_SQL = """\
INSERT INTO prospects (
    linkedin_url, first_name, last_name,
    headline, about, company, connection_degree, status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(linkedin_url) DO UPDATE SET
    first_name = COALESCE(excluded.first_name, first_name),
    last_name = COALESCE(excluded.last_name, last_name),
    headline = COALESCE(excluded.headline, headline),
    about = COALESCE(excluded.about, about),
    company = COALESCE(excluded.company, company),
    connection_degree = COALESCE(excluded.connection_degree, connection_degree),
    updated_at = CURRENT_TIMESTAMP
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def __enter__(self) -> Database:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- Prospects ---

    def upsert_prospects_batch(self, prospects: list[Prospect]) -> None:
        """Insert ou update une liste de prospects en une seule transaction."""
        with self.conn:
            self.conn.executemany(
                _UPSERT_PROSPECT_SQL,
                [
                    (
                        p.linkedin_url,
                        p.first_name,
                        p.last_name,
                        p.headline,
                        p.about,
                        p.company,
                        p.connection_degree,
                        p.status.value,
                    )
                    for p in prospects
                ],
            )

    def get_prospects_by_status(
        self, status: ProspectStatus, limit: int | None = None
    ) -> list[Prospect]:
        query = "SELECT * FROM prospects WHERE status = ? ORDER BY updated_at ASC"
        params: list = [status.value]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_prospect(r) for r in rows]

    def update_prospect_status(self, prospect_id: int, status: ProspectStatus) -> None:
        self.conn.execute(
            "UPDATE prospects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status.value, prospect_id),
        )
        self.conn.commit()

    def mark_synced(self, prospect_id: int) -> None:
        self.conn.execute(
            "UPDATE prospects SET synced_at = CURRENT_TIMESTAMP WHERE id = ?",
            (prospect_id,),
        )
        self.conn.commit()

    def get_unsynced_prospects(self, limit: int | None = None) -> list[Prospect]:
        query = "SELECT * FROM prospects WHERE synced_at IS NULL ORDER BY created_at ASC"
        params: list = []
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_prospect(r) for r in rows]

    def update_prospect_info(
        self,
        prospect_id: int,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        headline: str | None = None,
        about: str | None = None,
        company: str | None = None,
        connection_degree: str | None = None,
    ) -> None:
        fields = {
            "first_name": first_name,
            "last_name": last_name,
            "headline": headline,
            "about": about,
            "company": company,
            "connection_degree": connection_degree,
        }
        to_update = {k: v for k, v in fields.items() if v is not None}
        if not to_update:
            return
        set_clause = ", ".join(f"{k} = ?" for k in to_update)
        params = [*to_update.values(), prospect_id]
        self.conn.execute(
            f"UPDATE prospects SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            params,
        )
        self.conn.commit()

    def get_all_prospects(self) -> list[Prospect]:
        rows = self.conn.execute("SELECT * FROM prospects ORDER BY id").fetchall()
        return [self._row_to_prospect(r) for r in rows]

    def count_by_status(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM prospects GROUP BY status"
        ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    def get_messaged_prospects_for_followup(
        self, min_days: int, limit: int | None = None
    ) -> list[Prospect]:
        """Prospects messagés il y a au moins min_days jours, pas encore relancés."""
        query = """
            SELECT p.* FROM prospects p
            JOIN actions a ON a.prospect_id = p.id
            WHERE p.status = 'messaged'
              AND a.action_type = 'message'
              AND a.success = 1
              AND julianday('now') - julianday(a.created_at) >= ?
            ORDER BY a.created_at ASC
        """
        params: list = [min_days]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_prospect(r) for r in rows]

    def has_action(self, prospect_id: int, action_type: ActionType) -> bool:
        """Vérifie si une action réussie de ce type existe pour ce prospect."""
        row = self.conn.execute(
            "SELECT 1 FROM actions"
            " WHERE prospect_id = ? AND action_type = ? AND success = 1 LIMIT 1",
            (prospect_id, action_type.value),
        ).fetchone()
        return row is not None

    # --- Actions ---

    def log_action(self, action: Action) -> int:
        cursor = self.conn.execute(
            """INSERT INTO actions (prospect_id, action_type, message_sent, success, error)
            VALUES (?, ?, ?, ?, ?)""",
            (
                action.prospect_id,
                action.action_type.value,
                action.message_sent,
                int(action.success),
                action.error,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    # --- Daily Counters ---

    def increment_daily_counter(self, action_type: ActionType) -> int:
        today = date.today().isoformat()
        row = self.conn.execute(
            """INSERT INTO daily_counters (day, action_type, count)
            VALUES (?, ?, 1)
            ON CONFLICT(day, action_type) DO UPDATE SET count = count + 1
            RETURNING count""",
            (today, action_type.value),
        ).fetchone()
        self.conn.commit()
        return row[0] if row else 0

    def get_daily_count(self, action_type: ActionType) -> int:
        today = date.today().isoformat()
        row = self.conn.execute(
            "SELECT count FROM daily_counters WHERE day = ? AND action_type = ?",
            (today, action_type.value),
        ).fetchone()
        return row["count"] if row else 0

    # --- Helpers ---

    @staticmethod
    def _row_to_prospect(row: sqlite3.Row) -> Prospect:
        return Prospect(
            id=row["id"],
            linkedin_url=row["linkedin_url"],
            first_name=row["first_name"] or None,
            last_name=row["last_name"] or None,
            headline=row["headline"] or None,
            about=row["about"] or None,
            company=row["company"] or None,
            connection_degree=row["connection_degree"] or None,
            status=ProspectStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]).replace(tzinfo=UTC),
            updated_at=datetime.fromisoformat(row["updated_at"]).replace(tzinfo=UTC),
            synced_at=(
                datetime.fromisoformat(row["synced_at"]).replace(tzinfo=UTC)
                if row["synced_at"]
                else None
            ),
        )
