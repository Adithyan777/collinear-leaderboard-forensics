# controls/ — proof the grader cannot be fooled

These are not agent runs. They are deliberately bad test suites I built and
ran through the grader on purpose, to prove it rejects them. Two recorded
experiments:

**`mutant-proofs-and-lazy-suite.txt` — minimal effort fails.**
Two proofs in one file. First, every one of the 18 broken scorers is
genuinely catchable: the oracle suite kills each one. Second, a lazy
two-test suite (roughly "it runs without crashing" and "scores are between
0 and 1") catches only 2 of 16 — a hard fail. You cannot pass this task by
barely trying. The file also records which broken scorers were caught by
solvers that never saw them, the data behind the m16/m18 exclusion.

**`anti-grep-demo.txt` — cheating fails.**
The broken scorers are text edits of the correct one, so a cheating suite
could skip testing behavior and instead read the scorer's source file and
fail anything whose text looks different. To block this, the grader also
runs every suite against two extra correct scorers that behave identically
but are written differently (renamed variables, restructured code). A real
behavioral test passes them; a text-comparing cheat flags them as broken,
and falsely failing a correct scorer caps the score at 0.5 — automatic
fail. I built exactly such a cheat suite and ran it: it text-flagged 14 of
16 broken scorers but false-alarmed on both rewritten correct ones and was
capped at 0.5. The anti-cheat works.
