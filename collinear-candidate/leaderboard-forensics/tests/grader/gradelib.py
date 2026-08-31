"""Shared helpers for the grader checks."""

import csv
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reference"))
sys.path.insert(0, str(HERE.parent / "generator"))

import ref_scorer  # noqa: E402

TOL = 5e-5
N_EXAMPLES = 3996
SHARDS = [f"shard_{i:02d}" for i in range(12)]
MODELS = ["aurora-70b", "bramble-x", "cascade-2", "dune-mini", "ember-8x",
          "foxtail-pro"]


def load_gold(world):
    gold = {}
    with open(Path(world) / "data" / "gold" / "gold_labels.jsonl",
              encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            gold[r["example_id"]] = r["label"]
    return gold


def canonical_predictions(world, model):
    rows = []
    for shard in SHARDS:
        with open(Path(world) / "data" / "predictions" / f"{shard}.jsonl",
                  encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row["model"] == model:
                    rows.append(row)
    return rows


def reference_truth(world):
    """Per-model overall + ranking recomputed from raw data by ref_scorer."""
    gold = load_gold(world)
    overall = {}
    for model in MODELS:
        preds = canonical_predictions(world, model)
        overall[model] = ref_scorer.score_model(
            gold, preds, ref_scorer.TAXONOMY_WEIGHTS)["overall"]
    return overall, ref_scorer.rank_models(overall)


def parse_leaderboard(path):
    rank, overall = {}, {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rank[row["model"]] = int(row["rank"])
            overall[row["model"]] = float(row["overall"])
    return rank, overall


def db_query(db_path, sql, params=()):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()
