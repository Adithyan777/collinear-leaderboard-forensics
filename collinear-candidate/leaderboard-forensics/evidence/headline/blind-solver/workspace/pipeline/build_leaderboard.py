"""Aggregate the results DB into leaderboard.csv.

Usage: python -m pipeline.build_leaderboard
"""

import csv
import sys

from pipeline.config import CATEGORY_WEIGHTS, LEADERBOARD_PATH
from pipeline.data_io import connect
from pipeline.scorer import f1_from_counts, overall_from_category_f1, rank_models


def compute_scores(conn):
    """Per-model overall scores from per-example rows (SPEC sections 4-7)."""
    models = [r[0] for r in conn.execute("SELECT DISTINCT model FROM results ORDER BY model")]
    gold_present = {r[0] for r in conn.execute("SELECT DISTINCT gold_label FROM results")}
    scores = {}
    for model in models:
        counts = {c: {"tp": 0, "fp": 0, "fn": 0} for c in CATEGORY_WEIGHTS}
        cur = conn.execute(
            "SELECT gold_label, final_label FROM results WHERE model = ?", (model,)
        )
        for gold_label, final in cur:
            if final is None:
                counts[gold_label]["fn"] += 1
            elif final == gold_label:
                counts[gold_label]["tp"] += 1
            else:
                if final in counts:
                    counts[final]["fp"] += 1
                counts[gold_label]["fn"] += 1
        f1s = {c: f1_from_counts(**counts[c]) for c in CATEGORY_WEIGHTS}
        scores[model] = overall_from_category_f1(f1s, gold_present, CATEGORY_WEIGHTS)
    return scores


def main():
    conn = connect()
    scores = compute_scores(conn)
    ranking = rank_models(scores)
    with open(LEADERBOARD_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "model", "overall"])
        for i, model in enumerate(ranking, 1):
            w.writerow([i, model, f"{scores[model]:.4f}"])
    conn.close()
    print(f"wrote {LEADERBOARD_PATH}")


if __name__ == "__main__":
    sys.exit(main())
