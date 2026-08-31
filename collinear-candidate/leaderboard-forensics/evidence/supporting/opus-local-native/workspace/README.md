# Ticket-Triage Benchmark workspace

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
