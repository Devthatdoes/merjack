"""Local SQLite persistence: listing cache (dedupe + avoid re-fetching), saved
profiles/buy-boxes, and run history.

Listings are keyed by URL. Everything is stored as JSON blobs to stay schema-light
while the models evolve. Plain stdlib ``sqlite3`` — no ORM.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from .config import DB_PATH
from .models import BuyBox, Listing, MarketAssessment, Profile

_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    url        TEXT PRIMARY KEY,
    source     TEXT,
    fetched_at REAL,
    data       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    id   INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS buyboxes (
    name       TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    updated_at REAL
);
CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL,
    buybox     TEXT,
    summary    TEXT
);
CREATE TABLE IF NOT EXISTS market (
    key       TEXT PRIMARY KEY,
    cached_at REAL,
    data      TEXT NOT NULL
);
"""


@contextmanager
def _connect(path: str = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: str = DB_PATH) -> None:
    with _connect(path):
        pass


# --- Listings cache ------------------------------------------------------- #
def upsert_listing(listing: Listing, path: str = DB_PATH) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO listings(url, source, fetched_at, data) VALUES(?,?,?,?) "
            "ON CONFLICT(url) DO UPDATE SET source=excluded.source, "
            "fetched_at=excluded.fetched_at, data=excluded.data",
            (listing.url, listing.source, time.time(), listing.model_dump_json()),
        )


def get_listing(url: str, path: str = DB_PATH) -> Optional[Listing]:
    with _connect(path) as conn:
        row = conn.execute("SELECT data FROM listings WHERE url=?", (url,)).fetchone()
    return Listing.model_validate_json(row["data"]) if row else None


# --- Profile -------------------------------------------------------------- #
def save_profile(profile: Profile, path: str = DB_PATH) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO profiles(id, data) VALUES(1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
            (profile.model_dump_json(),),
        )


def load_profile(path: str = DB_PATH) -> Profile:
    with _connect(path) as conn:
        row = conn.execute("SELECT data FROM profiles WHERE id=1").fetchone()
    return Profile.model_validate_json(row["data"]) if row else Profile()


# --- Buy-boxes ------------------------------------------------------------ #
def save_buybox(name: str, buybox: BuyBox, path: str = DB_PATH) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO buyboxes(name, data, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
            (name, buybox.model_dump_json(), time.time()),
        )


def load_buybox(name: str, path: str = DB_PATH) -> Optional[BuyBox]:
    with _connect(path) as conn:
        row = conn.execute("SELECT data FROM buyboxes WHERE name=?", (name,)).fetchone()
    return BuyBox.model_validate_json(row["data"]) if row else None


# --- Run history ---------------------------------------------------------- #
def record_run(buybox: BuyBox, summary: dict, path: str = DB_PATH) -> int:
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO runs(started_at, buybox, summary) VALUES(?,?,?)",
            (time.time(), buybox.model_dump_json(), json.dumps(summary)),
        )
        return int(cur.lastrowid)


# --- Market assessment cache (keyed by industry|metro|month) -------------- #
def save_market(key: str, assessment: MarketAssessment, path: str = DB_PATH) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO market(key, cached_at, data) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET cached_at=excluded.cached_at, data=excluded.data",
            (key, time.time(), assessment.model_dump_json()),
        )


def get_market(key: str, max_age_days: float = 30, path: str = DB_PATH) -> Optional[MarketAssessment]:
    with _connect(path) as conn:
        row = conn.execute("SELECT cached_at, data FROM market WHERE key=?", (key,)).fetchone()
    if not row or (time.time() - row["cached_at"]) > max_age_days * 86_400:
        return None
    return MarketAssessment.model_validate_json(row["data"])
