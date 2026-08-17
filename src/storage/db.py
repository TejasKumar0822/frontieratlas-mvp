import json
import os
import sqlite3
from pathlib import Path

DB_PATH = Path("data/frontieratlas.db")
DB_PATH.parent.mkdir(exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    collected_at TEXT,
    payload TEXT NOT NULL,
    UNIQUE(record_type, canonical_key)
);
CREATE TABLE IF NOT EXISTS mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    method TEXT NOT NULL,
    score REAL
);
"""


def connect():
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    return con


def upsert_record(record_type: str, source_url: str, canonical_key: str, payload: dict, collected_at: str | None = None):
    con = connect()
    con.execute(
        "INSERT OR REPLACE INTO records(record_type,source_url,canonical_key,collected_at,payload) VALUES(?,?,?,?,?)",
        (record_type, source_url, canonical_key, collected_at, json.dumps(payload, ensure_ascii=False)),
    )
    con.commit(); con.close()


def add_mapping(mapping):
    con = connect()
    con.execute("INSERT INTO mappings(raw_name,canonical_name,entity_type,method,score) VALUES(?,?,?,?,?)", tuple(mapping.model_dump().values()))
    con.commit(); con.close()
