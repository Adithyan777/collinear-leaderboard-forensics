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
    """Shards that still need a scoring pass after an interrupted run."""
    completed = list(state["completed"])
    stuck = state.get("in_progress")
    if stuck:
        # The interrupted shard was mid-write when the run died; sqlite rolls
        # the open transaction back on reconnect, and that rollback can also
        # clip the tail of the previously committed batch in the same WAL
        # segment. So: settle the stuck shard, and redo the one before it to
        # be safe.
        completed.append(stuck)
        state["completed"] = completed
        state["in_progress"] = None
        save(state)
    redo = [completed[-2]] if len(completed) >= 2 else []
    todo = [s for s in shards if s not in completed]
    return redo + todo
