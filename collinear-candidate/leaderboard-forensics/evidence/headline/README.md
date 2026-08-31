# headline/ — the runs behind the results table

Every run here executed the shipped grader: 16 graded broken scorers,
kills >= 15, binary test_suite component.

| Folder | Solver | Result |
|--------|--------|--------|
| oracle-run-1/, oracle-run-2/ | Included oracle solution | 1.0, both times |
| blind-solver/ | Claude (Fable) agent, sealed sandbox, no knowledge of the broken scorers | 1.0 (16/16) |
| gpt-5.5-high/ | GPT-5.5-high in Codex | 0.70 FAIL (13/16) |
| opus-4.7/ | Claude Opus 4.7 in Claude Code | 0.70 FAIL (11/16) |

## How to read a Harbor run folder

`result.json` at the top level is the score summary. Inside the
`leaderboard-forensics__*/` job folder:

- `agent/` — the full agent transcript (every command and API message)
- `verifier/grader_detail.json` — the per-mutant kill matrix: exactly which
  broken scorers the suite caught and which survived
- `config.json`, `trial.log` — run configuration and timeline

## blind-solver/ is laid out differently

It ran in a sealed local sandbox, not as a Harbor job:

- `reward_shipped_grader.json` — its 1.0 score on the shipped grader
- `auditor-session-transcript.jsonl` — the full session
- `INTEGRITY.md` — the reproducible check that it never read any file
  outside the sandbox (no mutant or grader knowledge)
- `workspace/` — the exact work it produced
