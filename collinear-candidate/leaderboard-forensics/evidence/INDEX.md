# Evidence index

Every load-bearing claim in RUN_REPORT.md maps to a file here. All "headline"
runs executed the shipped grader (16 graded mutants, kills >= 15, binary
test_suite component). Per-mutant kill matrices: */verifier/grader_detail.json.

## headline/ — the final ladder (all physical)

| Claim | Path |
|---|---|
| Oracle passes, 1.0, twice | headline/oracle-run-1/, headline/oracle-run-2/ (result.json) |
| Blind agent (no design knowledge) passes 1.0, 16/16 | headline/blind-solver/reward_shipped_grader.json + workspace/ |
| Blind agent was genuinely blind | headline/blind-solver/INTEGRITY.md + auditor-session-transcript.jsonl |
| GPT-5.5-high fails 0.70 (13/16; survivors m11, m14, m17) | headline/gpt-5.5-high/ (result.json, verifier/grader_detail.json, agent/ trajectory) |
| Claude Opus 4.7 fails 0.70 (11/16; survivors m10, m11, m13, m14, m17) | headline/opus-4.7/ (same layout) |

## supporting/ — reproducibility and calibration history

| Claim | Path |
|---|---|
| Opus failed in a second environment (native CLI, local) | supporting/opus-local-native/ (session transcript + shipped-grader re-grade) |
| Opus failed at the v3 bar (12/18) | supporting/opus-trial3-18bar/ |
| GPT failed at the v3 bar (14/18) | supporting/gpt-18bar/ |
| Opus failed at the v2 bar (13/15) | supporting/opus-15bar/ |
| GPT PASSED at the v2 bar (14/15, 1.0) — honest calibration history | supporting/gpt-15bar-pass/ |
| Opus passed the v1 task (what triggered escalation) | supporting/opus-round1-pass/ |

## controls/

| Claim | Path |
|---|---|
| Lazy suite scores 2/16; every escalation mutant survives it | controls/mutant-proofs-and-lazy-suite.txt |
| Source-grepping cheat suite is capped at 0.5 | controls/anti-grep-demo.txt |
| All 18 mutants provably killable; m16/m18 excluded by blind-reachability | controls/mutant-proofs-and-lazy-suite.txt + ../tests/mutants/MUTANTS.md |
