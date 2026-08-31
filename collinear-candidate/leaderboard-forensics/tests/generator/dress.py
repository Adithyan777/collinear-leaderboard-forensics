"""World dressing: logs, ticket, README, RUNBOOK, CHANGELOG, July archive.
All timestamps are literals derived from the run-date constants; no wall clock.
"""

from pathlib import Path

RUN_DATE = "2026-08-12"
CRASH_T0 = (9, 14, 3)     # morning run start
RESUME_T0 = (9, 41, 17)   # resume start
SHARD_SECS = 87           # per-shard wall time in the logs


def _ts(base, plus_s):
    h, m, s = base
    total = h * 3600 + m * 60 + s + plus_s
    return f"{RUN_DATE} {total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _offsets(rng, n, start=2):
    """Cumulative per-line offsets: ~SHARD_SECS apart with seeded jitter."""
    t, out = start, []
    for _ in range(n):
        out.append(t)
        t += SHARD_SECS + rng.randrange(-9, 13)
    return out


def _lineno(workspace, relpath, needle):
    src = (Path(workspace) / relpath).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(src, 1):
        if needle in line:
            return i
    raise AssertionError(f"needle {needle!r} not found in {relpath}")


def write_crash_log(workspace, crash_lines, crash_shard, out_path, rng):
    ws = Path(workspace)
    offs = _offsets(rng, len(crash_lines))
    lines = [f"[{_ts(CRASH_T0, 0)}] scoring run starting (pid 41283)"]
    for i, msg in enumerate(crash_lines):
        lines.append(f"[{_ts(CRASH_T0, offs[i])}] {msg}")
    t_crash = offs[-1] + SHARD_SECS + rng.randrange(-20, 20)
    l_run = _lineno(workspace, "pipeline/run_scoring.py", "insert_rows(conn, rows)")
    l_io = _lineno(workspace, "pipeline/data_io.py", "conn.executemany(")
    lines += [
        f"[{_ts(CRASH_T0, t_crash)}] {crash_shard}: scoring",
        "Traceback (most recent call last):",
        f'  File "/app/workspace/pipeline/run_scoring.py", line {l_run}, in run',
        "    insert_rows(conn, rows)",
        f'  File "/app/workspace/pipeline/data_io.py", line {l_io}, in insert_rows',
        "    conn.executemany(",
        "sqlite3.OperationalError: disk I/O error",
    ]
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_resume_log(workspace, resume_lines, out_path, rng):
    offs = _offsets(rng, len(resume_lines))
    lines = [f"[{_ts(RESUME_T0, 0)}] scoring run starting (pid 41551)"]
    for i, msg in enumerate(resume_lines):
        lines.append(f"[{_ts(RESUME_T0, offs[i])}] {msg}")
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ticket(workspace, corrupted, july, out_path):
    """corrupted/july: {"rank": {model: int}, "overall": {model: float}}"""
    b_rank = corrupted["rank"]["bramble-x"]
    b_score = corrupted["overall"]["bramble-x"]
    jb_rank = july["rank"]["bramble-x"]
    jb_score = july["overall"]["bramble-x"]
    text = f"""# TICKET-4127: bramble-x leaderboard jump looks wrong

- **Filed:** 2026-08-13, support-ops (Priya N.)
- **Priority:** high -- vendor scorecards go out Friday
- **Component:** ticket-triage benchmark, August run

The August leaderboard (leaderboard.csv, and RESULTS.md) has **bramble-x at
rank {b_rank} with {b_score:.4f}**. In the July run it was rank {jb_rank} at
{jb_score:.4f} (docs/archive/RESULTS_2026-07.md). That is a big month-over-month
jump for a model the vendor hasn't updated since spring, and it doesn't match
what we see triaging with it day to day.

The one thing that did change on our side this cycle is the label
normalization update in `pipeline/normalize.py` (see docs/CHANGELOG.md,
2026-08-12 -- same day as the scoring run). I don't know the scoring internals,
but that's the only change on our side this cycle, so I suspect it's somehow
inflating bramble-x's numbers.

Can someone verify the scoring and re-issue the leaderboard before Friday?
I'd start with that normalize change.
"""
    Path(out_path).write_text(text, encoding="utf-8")


def write_readme(workspace):
    text = """# Ticket-Triage Benchmark workspace

Monthly scoring of vendor models on the support-ticket triage benchmark.

Layout:
- `data/gold/` -- gold labels (canonical taxonomy)
- `data/predictions/` -- vendor model outputs, 12 shards
- `pipeline/` -- scoring pipeline (see docs/SPEC.md for the scoring contract)
- `db/results.sqlite` -- per-example scoring rows from the latest run
- `leaderboard.csv`, `RESULTS.md` -- derived artifacts from the latest run
- `logs/` -- scoring run logs
- `state/checkpoint.json` -- scoring-run checkpoint (see docs/RUNBOOK.md)
- `tickets/` -- open tickets against this workspace

Common commands:

```
python -m pipeline.run_scoring            # fresh full scoring run
python -m pipeline.run_scoring --resume   # continue an interrupted run
python -m pipeline.build_leaderboard      # rebuild leaderboard.csv from the DB
python -m pipeline.report_md              # rebuild RESULTS.md from the DB
```
"""
    (Path(workspace) / "README.md").write_text(text, encoding="utf-8")


def write_runbook(workspace):
    text = """# Runbook -- monthly scoring run

1. Drop the vendor prediction shards into `data/predictions/`.
2. Run `python -m pipeline.run_scoring`. A full run takes a few minutes and
   commits one shard at a time; progress goes to `logs/`.
3. If the run is interrupted (box reboot, disk hiccup), rerun with
   `--resume`. The checkpoint in `state/checkpoint.json` records which shards
   have committed.
4. `python -m pipeline.build_leaderboard` then `python -m pipeline.report_md`.
5. Archive the previous month's RESULTS.md under `docs/archive/` before
   overwriting.

Scoring semantics live in docs/SPEC.md. That document is authoritative.
"""
    (Path(workspace) / "docs" / "RUNBOOK.md").write_text(text, encoding="utf-8")


def write_changelog(workspace):
    text = """# Changelog

- 2026-08-12: normalize: also map non-breaking spaces to ordinary spaces
  before collapsing (support-import tooling artifacts). (`pipeline/normalize.py`)
- 2026-07-28: report_md: include total row count in the header.
- 2026-07-15: July scoring run; archived to docs/archive/RESULTS_2026-07.md.
- 2026-06-20: checkpoint/resume support for interrupted runs.
- 2026-06-02: initial pipeline extracted from the old notebook.
"""
    (Path(workspace) / "docs" / "CHANGELOG.md").write_text(text, encoding="utf-8")


def write_july_archive(dest_md, scores, ranking, total_rows):
    lines = [
        "# Ticket-Triage Benchmark -- Monthly Results (2026-07-15)",
        "",
        f"Rows scored: {total_rows} across {len(scores)} models.",
        "Scoring per docs/SPEC.md (weighted per-category F1).",
        "",
        "| Rank | Model | Overall |",
        "|------|-------|---------|",
    ]
    for i, model in enumerate(ranking, 1):
        lines.append(f"| {i} | {model} | {scores[model]:.4f} |")
    lines += ["", "_Generated by pipeline/report_md.py._", ""]
    Path(dest_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
