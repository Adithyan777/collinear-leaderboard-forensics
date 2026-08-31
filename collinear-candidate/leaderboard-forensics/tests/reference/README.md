# reference/ — the correct scorers

- `ref_scorer.py` — the reference implementation of `docs/SPEC.md`. The
  broken scorers in `../mutants/` are edits of this file.
- `ref_variant_a.py`, `ref_variant_b.py` — the same behavior, rewritten:
  renamed variables, restructured code, identical answers on every input.

The variants exist as an anti-cheat. The agent's suite must pass all three.
A suite that tests behavior passes them automatically; a suite that
compares source text instead flags the variants as broken, and any false
alarm on a correct scorer caps the test_suite criterion at 0.5. The
recorded demonstration is in `../../evidence/controls/anti-grep-demo.txt`.
