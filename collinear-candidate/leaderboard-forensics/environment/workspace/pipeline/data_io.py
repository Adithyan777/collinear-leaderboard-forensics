"""JSONL + sqlite helpers."""

import json
import sqlite3

from pipeline.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    model TEXT NOT NULL,
    example_id TEXT NOT NULL,
    shard TEXT NOT NULL,
    gold_label TEXT NOT NULL,
    raw_label TEXT,
    final_label TEXT
);
"""


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def connect(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.execute(SCHEMA)
    return conn


def reset_db(conn):
    conn.execute("DROP TABLE IF EXISTS results")
    conn.execute(SCHEMA)
    conn.commit()


def insert_rows(conn, rows):
    conn.executemany(
        "INSERT INTO results (model, example_id, shard, gold_label, raw_label, final_label)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
