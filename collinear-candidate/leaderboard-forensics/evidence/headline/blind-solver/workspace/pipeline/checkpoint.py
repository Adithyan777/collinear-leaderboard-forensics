"""Scoring-run checkpoint state.

state/checkpoint.json tracks which shards have committed to the results DB so
an interrupted monthly run can resume instead of starting over.
"""

import json

from pipeline.config import CHECKPOINT_PATH


def load():
    try:
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"completed": [], "in_progress": None}


def save(state):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def set_in_progress(state, shard):
    state["in_progress"] = shard
    save(state)


def mark_done(state, shard):
    if shard not in state["completed"]:
        state["completed"].append(shard)
    state["in_progress"] = None
    save(state)


def resume_plan(state, shards):
    """Shards that still need a scoring pass after an interrupted run.

    A shard is done only once mark_done() recorded it in "completed"; every
    other shard still needs a scoring pass. In particular the shard recorded
    as in_progress was mid-write when the run died: sqlite rolls its open
    transaction back on reconnect (committed shards are untouched), so it must
    be re-scored, never settled as done. Shard writes are idempotent
    (see data_io.replace_shard_rows), so re-scoring a shard that committed but
    missed its mark_done is also safe and converges to one row per
    (model, gold example).
    """
    completed = set(state["completed"])
    if state.get("in_progress"):
        state["in_progress"] = None
        save(state)
    return [s for s in shards if s not in completed]
