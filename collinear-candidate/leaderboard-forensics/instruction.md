# Fix the August benchmark leaderboard

You are helping the eval-platform team at Meridian Labs. Their monthly
ticket-triage benchmark scores 6 vendor models; the August run is published in
`/app/workspace` (`leaderboard.csv`, `RESULTS.md`, `db/results.sqlite`).

Support-ops filed **`tickets/TICKET-4127.md`** questioning the August
leaderboard. Vendor scorecards go out Friday, so the team needs the numbers
verified, any real problem fixed at the root, and the leaderboard re-issued.

The scoring contract is **`docs/SPEC.md`** (authoritative). Ops procedures are
in `docs/RUNBOOK.md`. Everything you need is inside `/app/workspace`; there is
no network access.

## Deliverables

### 1. Root-cause fix in the pipeline

Investigate the August run and fix the actual root cause of any incorrect
scoring you find, in the pipeline code itself.

Constraints:
- `data/gold/` and `data/predictions/` are source data. Do not modify them.
- These commands must keep working, with unchanged interfaces:
  - `python -m pipeline.run_scoring` (fresh full run)
  - `python -m pipeline.run_scoring --resume` (continue an interrupted run)
  - `python -m pipeline.build_leaderboard`
- A run can be interrupted at any point; whatever the interruption point,
  rerunning with `--resume` must converge to the same correct final state
  (exactly one row per model per gold example).
- Grading runs your fixed pipeline end to end (all three commands above) on a
  **fresh copy of this benchmark with different data** and compares the
  outcome to an independent implementation of `docs/SPEC.md`. A hand-edited
  database with an unfixed pipeline will not pass.

### 2. Repaired artifacts

Repair the August artifacts so they reflect a correct scoring of `data/`
per `docs/SPEC.md`:

- `db/results.sqlite`: table `results` with columns
  `(model, example_id, shard, gold_label, raw_label, final_label)`, containing
  **exactly one row per (model, gold example)**. `final_label` is the
  normalized label, or NULL for an invalid/missing prediction.
- `leaderboard.csv`: header `rank,model,overall`, overall formatted to 4
  decimal places, ranked per SPEC §8.1.
- Regenerating `RESULTS.md` is good practice but is not graded.

### 3. Findings report

Write **`/app/workspace/report.json`** with exactly this schema (all numbers
computed from the data, not estimated):

```json
{
  "root_cause": {"file": "<pipeline file containing the bug>",
                  "function": "<function containing the bug>"},
  "shard_anomalies": [
    {"shard": "<shard_XX>", "defect": "<surplus_rows | missing_rows>",
     "n_rows": <int>}
  ],
  "corrected_overall": {"<model>": <float, 4dp, per SPEC rounding>, ...},
  "corrected_ranking": ["<model best first>", ...]
}
```

`shard_anomalies` definitions (a correct scoring produces exactly one row per
model per gold example of a shard in the `results` table):

- Include one entry for every shard whose row content in the **August**
  `results` table differs from a correct scoring of that shard; sort entries
  by shard name. If the August table were fully correct, the list would be
  empty.
- `"surplus_rows"`: the shard has more rows than a correct scoring;
  `n_rows` = the excess count.
- `"missing_rows"`: the shard has fewer rows than a correct scoring;
  `n_rows` = the shortfall count.

### 4. Acceptance tests for the scorer

Write a pytest suite in **`/app/workspace/acceptance_tests/`** that checks an
implementation of the scorer against `docs/SPEC.md`.

Contract:
- Tests import the implementation under test **only** as
  `from scorer_under_test import score_model, rank_models`
  (the grading harness places `scorer_under_test.py` next to your tests).
- Your suite will be run against **multiple scorer implementations: one
  correct, and several deliberately broken in different ways**. It should pass
  the correct implementation and fail every broken one. A suite that fails
  the correct implementation is heavily penalized, so only assert behavior
  the SPEC actually requires.
- At least 8 test functions. `pytest==8.4.1` is preinstalled; there is no
  network, so use only the standard library and pytest.

## Notes

- `docs/SPEC.md` is authoritative everywhere: for the pipeline fix, the
  repaired artifacts, the report, and your tests.
- The fresh grading copy follows the same structural conventions as the
  August data: the same 12 shards, every model appears in every shard file,
  and every prediction row for a gold example lives in that example's own
  shard file.
- Work happens in `/app/workspace`. Leave your deliverables at the exact
  paths above.
