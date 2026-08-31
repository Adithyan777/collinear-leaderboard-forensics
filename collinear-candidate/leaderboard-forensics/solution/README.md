# solution/ — the oracle solver

A known-good solution used only by Harbor's `oracle` agent. It proves the
task is solvable and the grader awards 1.0 to correct work. The agent under
evaluation never sees this folder.

`solve.sh` runs the four deliverables in order:

1. Copies `fixed/checkpoint.py` and `fixed/run_scoring.py` over the buggy
   pipeline files — the root-cause fix (correct resume logic plus idempotent
   shard writes, so a re-run can never double-write a shard).
2. Runs `oracle_repair.py`, which rebuilds `db/results.sqlite` and
   `leaderboard.csv` from the raw prediction data and writes `report.json`
   with the exact corrected numbers.
3. Copies `acceptance_tests/test_scorer_spec.py` into the workspace — the
   oracle acceptance suite, which kills all 18 broken scorers with zero
   false alarms. This is the existence proof that a suite meeting the bar
   can be written from `docs/SPEC.md` alone.
