# Runbook -- monthly scoring run

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
