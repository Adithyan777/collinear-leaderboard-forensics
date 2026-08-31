"""Scoring math for the ticket-triage benchmark.

Implements the contract in docs/SPEC.md (which is authoritative). The two
public entry points are score_model() and rank_models(); the small helpers
are shared with build_leaderboard so DB aggregation uses identical math.
"""

from decimal import Decimal, ROUND_HALF_UP

from pipeline.config import CATEGORY_WEIGHTS
from pipeline.normalize import normalize_label


def f1_from_counts(tp: int, fp: int, fn: int) -> float:
    denom = 2 * tp + fp + fn
    return (2 * tp / denom) if denom else 0.0  # SPEC 5.1


def round_overall(x: float) -> float:
    # SPEC 7.1. Built-in round() is banker's rounding; do not use it here.
    return float(Decimal(str(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def overall_from_category_f1(per_category_f1: dict, gold_present: set, weights: dict) -> float:
    num = sum(weights[c] * per_category_f1[c] for c in weights if c in gold_present)
    den = sum(weights[c] for c in weights if c in gold_present)  # SPEC 6.1/6.2
    return round_overall(num / den) if den else 0.0


def score_model(gold: dict, predictions: list, weights: dict) -> dict:
    """See docs/SPEC.md section 10 for the full contract."""
    seen = {}
    for row in predictions:
        eid = row["example_id"]
        if eid not in gold:
            continue  # SPEC 3.4
        if eid in seen:
            continue  # SPEC 3.3: first occurrence wins
        seen[eid] = row["label"]

    counts = {c: {"tp": 0, "fp": 0, "fn": 0} for c in weights}
    for eid, gold_label in gold.items():
        final = normalize_label(seen[eid]) if eid in seen else None
        valid = final in CATEGORY_WEIGHTS if final is not None else False
        if valid and final == gold_label:
            counts[gold_label]["tp"] += 1
        elif valid:
            if final in counts:
                counts[final]["fp"] += 1
            counts[gold_label]["fn"] += 1
        else:
            counts[gold_label]["fn"] += 1  # INVALID: FN only (SPEC 4.1)

    per_category = {
        c: {**counts[c], "f1": f1_from_counts(**counts[c])} for c in weights
    }
    overall = overall_from_category_f1(
        {c: per_category[c]["f1"] for c in weights}, set(gold.values()), weights
    )
    return {"per_category": per_category, "overall": overall}


def rank_models(overall_scores: dict) -> list:
    # SPEC 8.1: descending score; ties broken by name ascending.
    return [m for m, _ in sorted(overall_scores.items(), key=lambda kv: (-kv[1], kv[0]))]
