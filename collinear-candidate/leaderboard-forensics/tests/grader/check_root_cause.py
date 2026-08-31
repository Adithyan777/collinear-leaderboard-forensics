"""Criterion 1: the agent's FIXED pipeline, run on a held-out world with an
interrupted-and-resumed scoring run, produces the correct leaderboard.
Binary. Proves a general fix, not a hand-edited database."""

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gradelib  # noqa: E402
import ref_scorer  # noqa: E402


def build_crash_state(world, crash_idx, in_progress_committed=False):
    """Partial run state built with REFERENCE logic (agent-independent).

    Scenario A (in_progress_committed=False): crash mid-write of
    shards[crash_idx] -- its transaction rolled back, no rows committed.
    Scenario B (in_progress_committed=True): crash after shards[crash_idx]
    committed but before the checkpoint recorded it done -- its rows ARE in
    the DB while checkpoint.json still lists it as in_progress."""
    world = Path(world)
    gold = gradelib.load_gold(world)
    (world / "db").mkdir(exist_ok=True)
    (world / "state").mkdir(exist_ok=True)
    conn = sqlite3.connect(world / "db" / "results.sqlite")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS results (model TEXT NOT NULL, "
        "example_id TEXT NOT NULL, shard TEXT NOT NULL, gold_label TEXT NOT NULL,"
        " raw_label TEXT, final_label TEXT)")
    done = gradelib.SHARDS[:crash_idx]
    with_rows = (gradelib.SHARDS[:crash_idx + 1] if in_progress_committed
                 else done)
    for shard in with_rows:
        # first occurrence per (model, example) in file order (SPEC 3.3)
        first = {}
        with open(world / "data" / "predictions" / f"{shard}.jsonl",
                  encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                key = (row["model"], row["example_id"])
                if row["example_id"] in gold and key not in first:
                    first[key] = row["label"]
        lo = int(shard.split("_")[1]) * 333
        shard_gold = {f"tkt-{i:05d}": gold[f"tkt-{i:05d}"]
                      for i in range(lo, lo + 333)}
        rows = []
        for model in gradelib.MODELS:
            for eid in sorted(shard_gold):
                raw = first.get((model, eid))
                final = None
                if raw is not None:
                    f = ref_scorer.normalize_label(raw)
                    final = f if f in ref_scorer.TAXONOMY_WEIGHTS else None
                rows.append((model, eid, shard, shard_gold[eid], raw, final))
        conn.executemany("INSERT INTO results VALUES (?,?,?,?,?,?)", rows)
        conn.commit()
    conn.close()
    state = {"completed": done, "in_progress": gradelib.SHARDS[crash_idx]}
    with open(world / "state" / "checkpoint.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def _run_scenario(ws, base_world, crash_idx, scenario_dir, in_progress_committed,
                  fail, tag):
    world = scenario_dir
    shutil.copytree(base_world, world)
    shutil.copytree(ws / "pipeline", world / "pipeline")
    build_crash_state(world, crash_idx,
                      in_progress_committed=in_progress_committed)

    env = {"PYTHONPATH": str(world), "PYTHONHASHSEED": "0",
           "PATH": "/usr/local/bin:/usr/bin:/bin"}
    for cmd, tmo in [([sys.executable, "-m", "pipeline.run_scoring",
                       "--resume"], 240),
                     ([sys.executable, "-m", "pipeline.build_leaderboard"],
                      60)]:
        try:
            p = subprocess.run(cmd, cwd=world, env=env, timeout=tmo,
                               capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            fail(f"[{tag}] timeout running {' '.join(cmd[1:])}")
            return False
        if p.returncode != 0:
            fail(f"[{tag}] {' '.join(cmd[1:])} exited {p.returncode}: "
                 f"{p.stderr[-800:]}")
            return False

    ok = True
    db = world / "db" / "results.sqlite"
    counts = dict(gradelib.db_query(
        db, "SELECT model, COUNT(*) FROM results GROUP BY model"))
    for m in gradelib.MODELS:
        if counts.get(m) != gradelib.N_EXAMPLES:
            fail(f"[{tag}] held-out row count for {m}: {counts.get(m)}")
            ok = False
    dupes = gradelib.db_query(
        db, "SELECT COUNT(*) FROM (SELECT model, example_id FROM results "
            "GROUP BY model, example_id HAVING COUNT(*) > 1)")[0][0]
    if dupes:
        fail(f"[{tag}] held-out: {dupes} duplicated (model, example_id) pairs")
        ok = False

    ref_overall, ref_ranking = gradelib.reference_truth(world)
    lb = world / "leaderboard.csv"
    if not lb.exists():
        fail(f"[{tag}] held-out leaderboard.csv not produced")
        return False
    rank, overall = gradelib.parse_leaderboard(lb)
    for i, m in enumerate(ref_ranking, 1):
        if rank.get(m) != i:
            fail(f"[{tag}] held-out rank for {m}: {rank.get(m)} != {i}")
            ok = False
        if m in overall and abs(overall[m] - ref_overall[m]) > gradelib.TOL:
            fail(f"[{tag}] held-out overall for {m}: {overall[m]} != "
                 f"{ref_overall[m]}")
            ok = False
    return ok


def check(ws):
    ws = Path(ws)
    info = {"failures": []}
    fail = info["failures"].append

    import genworld
    from seeds import HELDOUT_SEEDS

    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "base"
        base.mkdir()
        seed = HELDOUT_SEEDS[0]
        crash_idx = genworld.crash_index(seed)
        genworld.build_clean_world(base, seed, genworld.MODELS_AUG,
                                   hot_shard=genworld.SHARDS[crash_idx - 1],
                                   cold_shard=genworld.SHARDS[crash_idx])
        # Scenario A: crash mid-write (interrupted shard has no rows).
        # Scenario B: crash after the shard committed but before the
        # checkpoint recorded it done. --resume must converge either way.
        _run_scenario(ws, base, crash_idx, Path(td) / "scenario_a", False,
                      fail, "scenario-A")
        _run_scenario(ws, base, crash_idx, Path(td) / "scenario_b", True,
                      fail, "scenario-B")
        info["heldout_seed"] = seed
        info["crash_idx"] = crash_idx
    return (1.0 if not info["failures"] else 0.0), info
