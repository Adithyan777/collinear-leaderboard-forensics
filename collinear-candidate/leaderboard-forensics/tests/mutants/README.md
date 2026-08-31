# mutants/ — the broken scorers

18 deliberately broken edits of `../reference/ref_scorer.py`. 16 are graded;
`mutant_16` and `mutant_18` are excluded from grading because no solver
without mutant knowledge ever caught them (the blind-reachability rule).

**[MUTANTS.md](MUTANTS.md)** documents every mutant: which SPEC clause it
breaks, the input that exposes it, and how many blind solvers caught it.
