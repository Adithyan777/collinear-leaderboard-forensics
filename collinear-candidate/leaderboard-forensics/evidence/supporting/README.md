# supporting/ — calibration history and the local rehearsal

These runs used earlier versions of the grader, kept as the honest record of
how the task was calibrated (full story in ../../RUN_REPORT.md, "Calibration
history"). Folder names: the number is how many broken scorers that grader
version used. v1 = 10, v2 = 15, v3 = 18, shipped = 16.

Per-mutant kill results are physical facts recorded at run time
(`verifier/grader_detail.json` inside each job folder); only the
threshold judging them changed between versions.

| Folder | What it shows |
|--------|---------------|
| opus-round1-pass/ | Opus 4.7 PASSED the v1 task (1.0) — the result that triggered escalation |
| opus-15bar/ | Opus failed the v2 grader (13/15) |
| gpt-15bar-pass/ | GPT-5.5-high PASSED the v2 grader (14/15, 1.0) — kept because honest calibration history includes passes |
| opus-trial3-18bar/ | Opus failed the v3 grader (12/18) |
| gpt-18bar/ | GPT failed the v3 grader (14/18) |
| opus-local-native/ | Opus 4.7 in the real Claude Code CLI on a sealed local copy — failed in a second, independent environment. `reward_shipped_grader.json` / `grader_detail_shipped.json` are its re-grade under the shipped grader; `RUN_META.md` documents the setup |
