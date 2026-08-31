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

    The interrupted (in_progress) shard was mid-write when the run died and
    its transaction rolled back, so it must be re-scored — never marked
    completed on its own. Shards written in earlier committed transactions
    are durable and are not redone.
    """
    completed = list(state["completed"])
    stuck = state.get("in_progress")
    redo = [stuck] if stuck and stuck not in completed else []
    todo = [s for s in shards if s not in completed and s != stuck]
    return redo + todo
