# expected/ — precomputed ground truth

What the grader compares the agent's work against:

- `leaderboard_ref.csv` — the correct August leaderboard, independently
  recomputed from the raw prediction data
- `report_expected.json` — the correct values for every machine-checked
  field of the agent's `report.json`
- `world_checksums.txt` — checksums of the generated workspace, proving the
  world the agent received is exactly what the generator produces
