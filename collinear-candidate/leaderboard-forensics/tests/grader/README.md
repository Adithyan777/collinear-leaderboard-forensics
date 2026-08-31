# grader/ — scoring logic

`main.py` orchestrates the four criteria and writes `reward.json` and
`grader_detail.json`. One checker per criterion:

- `check_root_cause.py` — runs the agent's fixed pipeline end-to-end on a
  fresh corrupted world built from a different seed, under two crash
  scenarios (mid-write rollback; rows committed but shard not marked done).
  A shallow fix that patches only the resume plan fails scenario B.
- `check_repair.py` — compares the rebuilt database and leaderboard against
  an independent recompute of the August data.
- `check_report.py` — validates `report.json`'s schema and compares every
  reported number within tolerance.
- `check_mutation.py` — runs the agent's acceptance suite against the 3
  correct scorers and the 16 graded broken ones. Pass requires kills >= 15
  with zero false alarms on any correct scorer.
- `gradelib.py` — shared helpers.
