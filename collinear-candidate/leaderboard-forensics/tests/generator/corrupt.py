"""Drive the (buggy) workspace pipeline through the crash + resume that
produced the corrupted August artifacts. Uses the real pipeline code so every
artifact is byte-consistent with what the team's run would have written.
"""

import sys
from pathlib import Path


def _import_pipeline(workspace):
    workspace = str(Path(workspace).resolve())
    for mod in [m for m in list(sys.modules) if m == "pipeline" or m.startswith("pipeline.")]:
        del sys.modules[mod]
    sys.path.insert(0, workspace)
    import pipeline.run_scoring as run_scoring  # noqa
    import pipeline.checkpoint as checkpoint  # noqa
    import pipeline.build_leaderboard as build_leaderboard  # noqa
    import pipeline.report_md as report_md  # noqa
    from pipeline.config import SHARDS  # noqa
    return run_scoring, checkpoint, build_leaderboard, report_md, SHARDS


def run_crash_and_buggy_resume(workspace, crash_idx, log_dir, run_date="2026-08-12"):
    """Returns (crash_log_lines, resume_log_lines, resume_plan_used)."""
    run_scoring, checkpoint, build_leaderboard, report_md, SHARDS = _import_pipeline(workspace)

    gold = run_scoring.load_gold()
    from pipeline.data_io import connect, insert_rows, reset_db

    # --- morning run: shards 0..crash_idx-1 commit, dies inside crash shard
    conn = connect()
    reset_db(conn)
    state = {"completed": [], "in_progress": None}
    checkpoint.save(state)
    crash_lines = [f"fresh run: scoring {len(SHARDS)} shards"]
    for shard in SHARDS[:crash_idx]:
        checkpoint.set_in_progress(state, shard)
        rows = run_scoring.score_shard(shard, gold)
        insert_rows(conn, rows)
        checkpoint.mark_done(state, shard)
        crash_lines.append(f"{shard}: committed {len(rows)} rows")
    crash_shard = SHARDS[crash_idx]
    checkpoint.set_in_progress(state, crash_shard)
    conn.close()

    # --- afternoon run: --resume with the buggy plan
    resume_lines = []
    run_scoring.run(resume=True, log=resume_lines.append)

    # --- derived artifacts from the corrupted DB
    build_leaderboard.main()
    report_md.main(["--run-date", run_date])
    return crash_lines, resume_lines, crash_shard


def make_crash_state(workspace, crash_idx):
    """Held-out variant: leave the world exactly at the moment of the crash
    (partial DB + checkpoint), with NO resume run. Verifier uses this."""
    run_scoring, checkpoint, _, _, SHARDS = _import_pipeline(workspace)
    gold = run_scoring.load_gold()
    from pipeline.data_io import connect, insert_rows, reset_db

    conn = connect()
    reset_db(conn)
    state = {"completed": [], "in_progress": None}
    checkpoint.save(state)
    for shard in SHARDS[:crash_idx]:
        checkpoint.set_in_progress(state, shard)
        rows = run_scoring.score_shard(shard, gold)
        insert_rows(conn, rows)
        checkpoint.mark_done(state, shard)
    checkpoint.set_in_progress(state, SHARDS[crash_idx])
    conn.close()
    return SHARDS[crash_idx]
