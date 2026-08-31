"""Criterion 2: repaired DB + leaderboard match an independent recomputation
of the raw data. Binary."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gradelib  # noqa: E402
import ref_scorer  # noqa: E402


def check(ws):
    ws = Path(ws)
    info = {"failures": []}
    fail = info["failures"].append

    ref_overall, ref_ranking = gradelib.reference_truth(ws)
    db = ws / "db" / "results.sqlite"
    if not db.exists():
        return 0.0, {"failures": ["db/results.sqlite missing"]}

    # exactly one row per (model, gold example)
    rows = gradelib.db_query(db, "SELECT model, COUNT(*) FROM results GROUP BY model")
    counts = dict(rows)
    for m in gradelib.MODELS:
        if counts.get(m) != gradelib.N_EXAMPLES:
            fail(f"row count for {m}: {counts.get(m)} != {gradelib.N_EXAMPLES}")
    dupes = gradelib.db_query(
        db, "SELECT COUNT(*) FROM (SELECT model, example_id FROM results "
            "GROUP BY model, example_id HAVING COUNT(*) > 1)")[0][0]
    if dupes:
        fail(f"{dupes} duplicated (model, example_id) pairs remain")

    # recompute overall from the DB rows with reference math
    gold = gradelib.load_gold(ws)
    gold_present = set(gold.values())
    weights = ref_scorer.TAXONOMY_WEIGHTS
    for m in gradelib.MODELS:
        counts_c = {c: {"tp": 0, "fp": 0, "fn": 0} for c in weights}
        for gold_label, final in gradelib.db_query(
                db, "SELECT gold_label, final_label FROM results WHERE model = ?",
                (m,)):
            if final is None:
                counts_c[gold_label]["fn"] += 1
            elif final == gold_label:
                counts_c[gold_label]["tp"] += 1
            else:
                if final in counts_c:
                    counts_c[final]["fp"] += 1
                counts_c[gold_label]["fn"] += 1
        f1s = {c: (2 * v["tp"] / (2 * v["tp"] + v["fp"] + v["fn"])
                   if (2 * v["tp"] + v["fp"] + v["fn"]) else 0.0)
               for c, v in counts_c.items()}
        num = sum(weights[c] * f1s[c] for c in weights if c in gold_present)
        den = sum(weights[c] for c in weights if c in gold_present)
        got = ref_scorer.round_overall(num / den)
        if abs(got - ref_overall[m]) > gradelib.TOL:
            fail(f"DB-derived overall for {m}: {got} != {ref_overall[m]}")

    # spot-check normalization on a deterministic sample of rows
    import random
    rng = random.Random(4127)
    sample_ids = [f"tkt-{rng.randrange(gradelib.N_EXAMPLES):05d}" for _ in range(60)]
    for m in gradelib.MODELS[:3]:
        preds = gradelib.canonical_predictions(ws, m)
        first = {}
        for row in preds:
            if row["example_id"] in gold and row["example_id"] not in first:
                first[row["example_id"]] = row["label"]
        for eid in sample_ids[:20]:
            expect = None
            if eid in first:
                f = ref_scorer.normalize_label(first[eid])
                expect = f if f in ref_scorer.TAXONOMY_WEIGHTS else None
            got = gradelib.db_query(
                db, "SELECT final_label FROM results WHERE model=? AND example_id=?",
                (m, eid))
            if len(got) != 1 or got[0][0] != expect:
                fail(f"final_label for ({m}, {eid}): {got} != {expect}")
                break

    # leaderboard.csv
    lb = ws / "leaderboard.csv"
    if not lb.exists():
        fail("leaderboard.csv missing")
    else:
        rank, overall = gradelib.parse_leaderboard(lb)
        for i, m in enumerate(ref_ranking, 1):
            if rank.get(m) != i:
                fail(f"leaderboard rank for {m}: {rank.get(m)} != {i}")
            if m in overall and abs(overall[m] - ref_overall[m]) > gradelib.TOL:
                fail(f"leaderboard overall for {m}: {overall[m]} != {ref_overall[m]}")

    info["ref_ranking"] = ref_ranking
    return (1.0 if not info["failures"] else 0.0), info
