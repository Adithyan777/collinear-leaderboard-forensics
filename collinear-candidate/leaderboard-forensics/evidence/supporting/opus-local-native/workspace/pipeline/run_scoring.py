"""Score all prediction shards against gold and write per-example rows.

Usage:
    python -m pipeline.run_scoring            # fresh full run (rebuilds the DB)
    python -m pipeline.run_scoring --resume   # continue an interrupted run
"""

import argparse
import sys

from pipeline import checkpoint
from pipeline.config import (
    CATEGORY_WEIGHTS,
    GOLD_PATH,
    PREDICTIONS_DIR,
    SHARDS,
    shard_of,
)
from pipeline.data_io import connect, read_jsonl, replace_shard, reset_db
from pipeline.normalize import normalize_label


def load_gold():
    return {row["example_id"]: row["label"] for row in read_jsonl(GOLD_PATH)}


def score_shard(shard, gold):
    """Build result rows for one shard. Returns list of DB tuples."""
    rows_by_model = {}
    for row in read_jsonl(PREDICTIONS_DIR / f"{shard}.jsonl"):
        eid = row["example_id"]
        if eid not in gold:
            continue  # stray id: contributes nothing (SPEC 3.4)
        if shard_of(eid) != shard:
            continue
        per_model = rows_by_model.setdefault(row["model"], {})
        if eid in per_model:
            continue  # duplicate: first occurrence wins (SPEC 3.3)
        per_model[eid] = row["label"]

    shard_gold = {eid: g for eid, g in gold.items() if shard_of(eid) == shard}
    models = sorted(rows_by_model)
    out = []
    for model in models:
        preds = rows_by_model[model]
        for eid in sorted(shard_gold):
            raw = preds.get(eid)
            if raw is None:
                final = None  # missing prediction: INVALID (SPEC 3.2)
            else:
                final = normalize_label(raw)
                if final not in CATEGORY_WEIGHTS:
                    final = None  # non-taxonomy label: INVALID (SPEC 3.1)
            out.append((model, eid, shard, shard_gold[eid], raw, final))
    return out


def run(resume=False, log=print):
    gold = load_gold()
    state = checkpoint.load()
    conn = connect()
    if resume:
        plan = checkpoint.resume_plan(state, SHARDS)
        log(f"resume: {len(state['completed'])} shards recorded done")
    else:
        reset_db(conn)
        state = {"completed": [], "in_progress": None}
        checkpoint.save(state)
        plan = list(SHARDS)
        log(f"fresh run: scoring {len(plan)} shards")
    for shard in plan:
        checkpoint.set_in_progress(state, shard)
        rows = score_shard(shard, gold)
        replace_shard(conn, shard, rows)
        checkpoint.mark_done(state, shard)
        log(f"{shard}: committed {len(rows)} rows")
    conn.close()
    log("scoring complete")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)
    run(resume=args.resume)


if __name__ == "__main__":
    sys.exit(main())
