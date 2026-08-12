"""SQLite-backed persistence so monthly uploads accumulate across sessions."""

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "ino_ops.db"

COLUMNS = [
    "period",
    "uploaded_at",
    "issue_key",
    "issue_id",
    "summary",
    "assignee",
    "assignee_id",
    "reporter",
    "reporter_id",
    "status",
    "status_group",
    "is_closed",
    "priority",
    "updated",
    "due_date",
    "month",
    "team",
    "story_points",
]


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS issues (
                period TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                issue_key TEXT NOT NULL,
                issue_id TEXT,
                summary TEXT,
                assignee TEXT,
                assignee_id TEXT,
                reporter TEXT,
                reporter_id TEXT,
                status TEXT,
                status_group TEXT,
                is_closed INTEGER,
                priority TEXT,
                updated TEXT,
                due_date TEXT,
                month TEXT,
                team TEXT,
                story_points REAL,
                PRIMARY KEY (period, issue_key)
            )
            """
        )


def save_period(df: pd.DataFrame, period: str) -> int:
    """Replace any existing rows for `period` with the newly uploaded snapshot."""
    out = df.copy()
    out["period"] = period
    out["uploaded_at"] = datetime.now().isoformat(timespec="seconds")
    out["updated"] = out["updated"].astype(str)
    out["due_date"] = out["due_date"].astype(str)
    out["is_closed"] = out["is_closed"].astype(int)
    out = out[COLUMNS]

    with _connect() as conn:
        conn.execute("DELETE FROM issues WHERE period = ?", (period,))
        out.to_sql("issues", conn, if_exists="append", index=False)
    return len(out)


def list_periods() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql(
            """
            SELECT period,
                   COUNT(*) AS issue_count,
                   MAX(uploaded_at) AS uploaded_at,
                   MIN(updated) AS min_updated,
                   MAX(updated) AS max_updated
            FROM issues
            GROUP BY period
            ORDER BY period DESC
            """,
            conn,
        )
    return df


def delete_period(period: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM issues WHERE period = ?", (period,))


def load_data(periods: list[str] | None = None) -> pd.DataFrame:
    with _connect() as conn:
        if periods:
            placeholders = ",".join("?" for _ in periods)
            df = pd.read_sql(
                f"SELECT * FROM issues WHERE period IN ({placeholders})", conn, params=periods
            )
        else:
            df = pd.read_sql("SELECT * FROM issues", conn)

    if df.empty:
        return df

    df["updated"] = pd.to_datetime(df["updated"], errors="coerce")
    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["is_closed"] = df["is_closed"].astype(bool)
    return df
