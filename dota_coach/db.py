import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    discord_id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    discord_id INTEGER NOT NULL,
    account_id INTEGER,
    match_id INTEGER NOT NULL,
    hero TEXT,
    metrics TEXT NOT NULL,
    advice TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS match_metrics (
    account_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    metrics TEXT,  -- NULL = parsed but not a usable mid game; don't refetch
    PRIMARY KEY (account_id, match_id)
);
"""


class DB:
    def __init__(self, path="dota_coach.db"):
        self._c = sqlite3.connect(path)
        self._c.executescript(SCHEMA)

    def link(self, discord_id, account_id):
        with self._c:
            self._c.execute(
                "INSERT INTO users VALUES (?, ?) ON CONFLICT(discord_id) DO UPDATE SET account_id=excluded.account_id",
                (discord_id, account_id),
            )

    def account_id(self, discord_id):
        row = self._c.execute("SELECT account_id FROM users WHERE discord_id=?", (discord_id,)).fetchone()
        return row[0] if row else None

    def save_review(self, discord_id, account_id, match_id, metrics, advice):
        with self._c:
            self._c.execute(
                "INSERT INTO reviews (discord_id, account_id, match_id, hero, metrics, advice) VALUES (?,?,?,?,?,?)",
                (discord_id, account_id, match_id, metrics.get("hero"), json.dumps(metrics), advice),
            )

    def get_metrics(self, account_id, match_id):
        """(cached, metrics): cached False = never seen; metrics None = seen but skipped."""
        row = self._c.execute(
            "SELECT metrics FROM match_metrics WHERE account_id=? AND match_id=?", (account_id, match_id)
        ).fetchone()
        return (True, json.loads(row[0]) if row[0] else None) if row else (False, None)

    def save_metrics(self, account_id, match_id, metrics):
        with self._c:
            self._c.execute(
                "INSERT OR REPLACE INTO match_metrics VALUES (?,?,?)",
                (account_id, match_id, json.dumps(metrics) if metrics else None),
            )
