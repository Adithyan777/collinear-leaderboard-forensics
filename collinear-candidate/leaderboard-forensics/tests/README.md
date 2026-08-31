# tests/ — the hidden verifier

Nothing in this folder is visible to the agent while it works. Harbor mounts
it at `/tests` only after the agent's session ends. The answer key and the
network are never available at the same time.

`grader/main.py` is the entry point: it scores the agent's workspace and
writes `reward.json` (four criteria) plus `grader_detail.json` (the
per-mutant kill matrix).

- [grader/](grader/) — the four criterion checkers and the scoring logic
- [reference/](reference/) — the correct scorer, plus two rewritten copies
  that behave identically (the anti-cheat against text-matching suites)
- [mutants/](mutants/) — the 18 broken scorers (16 graded, 2 excluded);
  see `mutants/MUTANTS.md` for what each one breaks
- [generator/](generator/) — the seeded generator that built the entire
  task world; reruns produce byte-identical output
- [expected/](expected/) — precomputed ground truth the grader compares
  against
