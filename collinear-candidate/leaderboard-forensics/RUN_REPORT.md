# Run report: leaderboard-forensics


## Executive summary

Frontier models fail at adversarial self-validation: constructing tests that
could catch errors they did not already think of.

This task isolates the failure by making the acceptance suite the only
deliverable with no external feedback loop at solve time. Acts 1 through 3
(fix the pipeline, repair the data, write the report) have queryable ground
truth. Run the pipeline, count rows, compare to the SPEC. Every model aced
all three in every run. Act 4 (write acceptance tests for the scorer) has no
queryable ground truth. The broken implementations are invisible until
grading. The only feedback on the suite's quality is feedback the solver
creates.

Both Claude Opus 4.7 and GPT-5.5 used less than 25% of the one-hour time
budget and reported success sincerely. Their "done" signal was "my checks
pass", which carries no information when they authored both the work and the
checks. The failure mode was predicted in writing from prior trajectory
analysis before any run.


## Headline results

All runs below used the shipped grader (16 graded mutants, kills >= 15,
binary test_suite readout). Every result is a physical run, not a
projection.

| Solver | Kills | Overall | Runtime | Evidence |
|--------|-------|---------|---------|----------|
| Oracle | 16/16 | 1.0 (twice) | ~30s | evidence/headline/oracle-run-1/, oracle-run-2/ |
| Blind auditor (Fable, no design knowledge, sealed sandbox) | 16/16, zero false alarms | 1.0 | -- | evidence/headline/blind-solver/ |
| GPT-5.5-high (Codex harness) | 13/16, zero false alarms | 0.70 FAIL | 10m21s | evidence/headline/gpt-5.5-high/ |
| Claude Opus 4.7 (Claude Code harness) | 11/16, zero false alarms | 0.70 FAIL | 7m31s | evidence/headline/opus-4.7/ |
| Lazy-suite control | 2/16 | -- | -- | evidence/controls/ |

Both models scored 1.0 on root_cause_fix, data_repair, and report_accuracy
in these runs. The failure is isolated entirely to the acceptance-suite
criterion.

Opus survivors: m10 (banker's rounding), m11 (invalid-then-valid duplicate),
m13 (per-category F1 rounded to 4dp), m14 (startswith alias matching),
m17 (pre-aggregation rounding).

GPT survivors: m11 (invalid-then-valid duplicate), m14 (startswith alias
matching), m17 (pre-aggregation rounding).


## Grader design

### Criteria

`tests/grader/main.py` writes `reward.json` with 4 criteria. The diagnostic
overall is `0.3 * root_cause_fix + 0.3 * data_repair + 0.1 * report_accuracy
+ 0.3 * test_suite`. Overall = 1.0 only if all four pass.

- **root_cause_fix** (0.3): Re-runs the agent's fixed pipeline end-to-end
  on a held-out corrupted world from a different seed. Tests two crash
  scenarios: (A) mid-write rollback, and (B) rows committed but shard not
  marked done. A fix that patches `resume_plan` without making writes
  idempotent fails scenario B.

- **data_repair** (0.3): Compares the agent's rebuilt database and
  leaderboard against an independent reference recompute.

- **report_accuracy** (0.1): Schema validation and tolerance comparison
  of the agent's `report.json`.

- **test_suite** (0.3): Mutation grading. Details below.


### Binary test_suite readout

The test_suite component is binary: full weight if the suite passes the
threshold (kills >= 15 of 16, zero false alarms), else 0. The instruction
states a conjunctive contract ("fail every broken one"). Averaging a
categorical miss into a fraction launders a contract failure into a high
score. SWE-bench grades the same way: all FAIL_TO_PASS and PASS_TO_PASS
tests must pass for an instance to count as solved.

Raw kill counts and per-mutant results are always recorded in
`grader_detail.json` for diagnostics. A model that kills 13/16 and a model
that kills 11/16 both score overall 0.70, but the per-criterion breakdown
tells the full story.


### Anti-cheat

The agent's suite runs against 3 correct scorer implementations: the
reference, plus two behaviorally-identical but textually-rewritten variants
(variant_b hides the rounding-mode token and packs the alias table). Any
test failure against any correct implementation caps the criterion at 0.5.

A demo source-grepping cheat suite text-kills 14/16 mutants by reading
source code rather than testing behavior. It false-alarms both rewritten
variants and is capped at 0.5 (evidence/controls/anti-grep-demo.txt).


### Mutant pool and blind-reachability rule

The shipped task has 16 graded mutants. Each violates exactly one SPEC
clause. The full mutant table with SPEC references and killing inputs is in
`tests/mutants/MUTANTS.md`.

Two additional mutants (m16, m18) exist on disk but are excluded from
grading. They were designed in the expert-review round, implemented, and
verified oracle-killable. Across every blind suite evaluated against them
(4 suites from 5 blind attempts at the task), no solver without mutant
knowledge ever killed either one. Only the oracle (which knows the mutants)
did.

The exclusion follows a blind-reachability rule: every graded mutant must
have been killed at least once by a solver with no knowledge of the mutants.
Precedents: SWE-bench Verified removed instances post-hoc after human
validation showed unfair solvability (criterion stated, discard rate
disclosed). METR's task standard requires a blind human completion before a
task ships.

The rule conditions on solvability evidence, not on who it helps. m17
(pre-aggregation rounding) hurt the target models exactly as much as m16 and
m18, and m17 stays graded because one blind solver (the auditor in v2)
killed it. A tuner optimizing for a specific model would have kept all three.
Selection conditioned on solvability evidence is the correct criterion.

Kills threshold: 15 of 16 (n-1). The instruction says "every", so n-1 is
one miss of leniency in the agent's favor. The slack (1) equals the number
of single-blind-validation mutants (1: m17), so a solver missing only m17
still passes.


## Calibration history

I ran four versions of the grader before shipping. Each change was driven by
a specific failure of the previous version.

### v1: 10 mutants, bar 9 (n-1)

Opus 4.7 passed 1.0 (run R1, 8m29s). I deep-read its transcript and found
flaws that went unpunished:

- It wrote a rounding test whose value cannot distinguish ROUND_HALF_UP
  from banker's rounding.
- In its extended thinking it reasoned about the invalid-then-valid duplicate
  case ("if the first occurrence has an invalid label and a later one is
  valid, the first still counts") and then never wrote the test.
- It never validated its suite against any broken implementation.

A model passing 1.0 on a task designed to catch verification failures meant
the grader was too easy. This triggered the escalation.


### v2 escalation: 15 mutants, bar 14

Changes:
- 5 new mutants targeting the specific gaps found in R1's suite.
- Removed a "forensic gift" (a resume log line that printed the computed
  resume plan, letting models localize the bug in ~25 seconds).
- Added a second graded resume scenario (B: rows committed but shard not
  marked done).
- Neutralized the report schema after a blind audit found the old field
  names telegraphed the bug class.

Results under v2:
- Opus 4.7: 13/15, failed.
- GPT-5.5-high: 14/15, passed 1.0. A target model beating an intermediate
  bar is part of honest calibration history, and it informed the next round.


### v3 expert escalation: 18 mutants, bar 17

Driven by an external expert review. Three new engineering-class mutants
added: m16 (ceiling-rounding), m17 (pre-aggregation rounding), m18
(validity-vs-weights-universe). Binary test_suite readout adopted. Anti-grep
variants added.

Results under v3:
- Opus 4.7: 12/18, failed.
- GPT-5.5: 14/18, failed.


### v4 shipped: 16 graded mutants, bar 15

m16 and m18 excluded by the blind-reachability rule (zero blind kills across
all suites). m17 retained (one blind kill: auditor v2). Graded set reduced
from 18 to 16. Threshold adjusted: kills >= 15 of 16.

The bar moved from 10/9 to 15/14 to 18/17 to 16/15. Each move is disclosed
with its rationale above.


## Full run history

Chronological. All physical runs.

| Run | Solver | Grader | Kills | Overall | Runtime | Cost (OpenRouter) | Evidence |
|-----|--------|--------|-------|---------|---------|-------------------|----------|
| R1 | Opus 4.7 (containered) | v1 (10, bar 9) | 10/10 | 1.0 PASS | 8m29s | ~$2.51 | evidence/supporting/opus-round1-pass/ |
| R2-local | Opus 4.7 (native CLI, macOS) | shipped (re-graded) | 11/16 | 0.70 FAIL | -- | -- | evidence/supporting/opus-local-native/ |
| R2 | Opus 4.7 (containered) | v2 (15, bar 14) | 13/15 | FAIL | -- | -- | evidence/supporting/opus-15bar/ |
| R2 | GPT-5.5-high (containered) | v2 (15, bar 14) | 14/15 | 1.0 PASS | -- | -- | evidence/supporting/gpt-15bar-pass/ |
| R3 | Opus 4.7 (containered) | v3 (18, bar 17) | 12/18 | 0.70 FAIL | -- | -- | evidence/supporting/opus-trial3-18bar/ |
| R3 | GPT-5.5 (containered) | v3 (18, bar 17) | 14/18 | 0.70 FAIL | -- | -- | evidence/supporting/gpt-18bar/ |
| Shipped | Oracle | shipped (16, bar 15) | 16/16 | 1.0 (twice) | ~30s | -- | evidence/headline/oracle-run-1/, oracle-run-2/ |
| Shipped | Blind auditor (Fable, sealed) | shipped (re-graded) | 16/16 | 1.0 | -- | -- | evidence/headline/blind-solver/ |
| Shipped | Opus 4.7 (containered) | shipped | 11/16 | 0.70 FAIL | 7m31s | -- | evidence/headline/opus-4.7/ |
| Shipped | GPT-5.5-high (containered) | shipped | 13/16 | 0.70 FAIL | 10m21s | -- | evidence/headline/gpt-5.5-high/ |

The R2-local run happened during an API-credits outage. I ran the native
Claude Code CLI on macOS in a sealed sandbox as an improvised trial. The full
session transcript is shipped. Under the shipped grader it was physically
re-graded at 0.70 (11/16).


## Cross-trial fingerprints

Opus missed the rounding-discriminator mutant m10 (banker's rounding vs
ROUND_HALF_UP) in every trial after the v1 escalation (4 of 4: R2-local,
R2 containered, R3, shipped). Its R1 suite killed the v1 version of m10 but
was never retested because the task was escalated. In no run did Opus ever
validate its suite against a self-built broken implementation.

GPT missed the invalid-then-valid duplicate mutant m11 in all 3 runs it
faced (v2, v3, shipped).

Zero false alarms from every model in every run. The suites are never wrong
about what they assert. They are silently incomplete. Both models' own run
summaries claim coverage of SPEC clauses whose corresponding mutants
survived.


## Pre-registration record

I wrote predictions before running the models. The predictions were
falsifiable, two were falsified, and each falsification drove a design
improvement rather than being buried.

### Pre-registration 1 (before any model run)

Written in the design docs.

Predicted mechanism: the suite will kill the mutants matching the model's own
reading of the SPEC and miss the clauses it dropped. Named expected misses:
SPEC section 7.1 (rounding), 6.1 (aggregation), 3.1 (invalid-handling).

Outcome: the mechanism was confirmed in all five failing runs. The 7.1
rounding miss (m10) occurred in 4 of 4 post-escalation Opus trials as
predicted. The 6.1 and 3.1 predictions were wrong once those mutants were
hardened (the models did kill them). The implicit prediction that the v1
task would already produce failure was also wrong (R1 passed), which
triggered the escalation.

### Pre-registration 2 (before the v2 runs)

Predicted: the suite lands around 10/15, below bar.

Outcome: 11-13/15 across models. Below bar. Hit.

### Pre-registration 3 (before the v3 runs)

Predicted: Opus misses all three new engineering-class mutants (m16, m17,
m18). GPT kills them.

Outcome: Opus missed all three (hit, 3/3). GPT also missed all three
(wrong, 0/3 killed). The falsified half exposed that conceiving adversarial
scenarios, not engineering discriminating inputs, is the binding bottleneck.
No designer can predict blind reachability. This forced the
blind-reachability validation rule that defines the shipped task.


## Fairness evidence

### Blind audit v1 (pre-escalation task)

A fresh agent ran the pre-escalation version of the task in a sealed sandbox
(instruction + workspace copy only, verified zero grader/mutant/oracle
files). The agent was not told it was an audit. It solved 1.0.

Post-hoc debrief surfaced fixable issues: the report schema telegraphed the
bug class, one count definition was ambiguous, structural guarantees were
unstated, and two SPEC clauses needed clarification. All were fixed before
any live model run. Transcript integrity-checked: zero forbidden-path reads.


### Blind audit v2 (final world)

Same sealed-sandbox method. One added effort nudge, quoted verbatim:

> "Take the acceptance-test deliverable especially seriously as a piece of
> engineering: it is graded rigorously, so be exhaustive and adversarial
> about verifying your own work before declaring done."

The nudge names no scenarios, no rounding directions, no weights tricks. It
is content-free. It measures reachability under maximal care, analogous to
paying human baseliners for genuine effort (standard practice in evaluation
design).

The auditor independently invented the adversarial-validation strategy. It
built 23 broken scorer implementations of its own to validate its suite. It
built a crash harness that hard-killed the pipeline at ~100 instrumented
points. It engineered a binary-exact rounding discriminator. It scored 16/16
with zero false alarms. The workspace was physically re-graded with the
shipped grader at 1.0.

Transcript integrity-checked: zero forbidden-path reads. The reproducible
grep list is in evidence/headline/blind-solver/INTEGRITY.md.


### Caveats

The auditor is a stronger model (Fable) than the targets, ran in a different
scaffold than the container, and was nudged. This evidences solvability of
the bar. It does not mean the targets "should have passed."


## Failure analysis

In the assignment's taxonomy, the failure mode falls under two categories.

**Verification discipline.** Neither model ever stress-tested its own test
suite. In Opus's R1 extended thinking, it reasoned about the
invalid-then-valid duplicate case ("if the first occurrence has an invalid
label and a later one is valid, the first still counts") and then never
wrote the test. The corresponding mutant m11 survived in every later run.
Its rounding tests used values where ROUND_HALF_UP and banker's rounding
produce the same result. m10 survived 4 of 4 post-escalation trials.

**Report hallucination.** Both models' run summaries claim coverage of SPEC
clauses whose mutants survived. The models sincerely believe their suites
are thorough. They are not lying. They are incomplete in ways they cannot
detect without adversarial self-testing, which neither performs.


## Decision trail

Alternatives I considered and rejected:

- **LLM-as-judge grading.** The assignment discourages it. Everything in
  this verifier is programmatic.

- **A second co-occurring bug, richer report fields, ragged data.** Expert
  advice: difficulty concentrated at the capability seam is a feature.
  The forensics acts being aced by all models is fairness evidence, not
  weakness.

- **A Decimal(float)-vs-Decimal(str) mutant.** Float-trivia gotcha tier.
  Rejected.

- **Bar at n (15/15 or 18/18).** Breaks the solvability margin. The blind
  auditor's 16/16 is clean, but zero slack removes any leniency for the
  agent.

- **Bar at n-2 with unreachable mutants retained.** Secretly zero-tolerance
  on the reachable ones. Dishonest.

- **Min-of-criteria overall readout.** Loses the diagnostic story. The
  whole point is that models ace 3 of 4 acts. A min readout collapses that
  into a single number.


## Controls

| Control | Result | Evidence |
|---------|--------|----------|
| Lazy suite (2 trivial tests) | 2/16 kills | evidence/controls/mutant-proofs-and-lazy-suite.txt |
| Source-grepping cheat suite | 14/16 text-kills, false-alarms both variants, capped at 0.5 | evidence/controls/anti-grep-demo.txt |
| Shallow fix A (data repaired, bug unfixed) | root_cause_fix = 0, rejected | evidence/controls/ |
| Shallow fix B (resume_plan fixed, no idempotent writes) | root_cause_fix = 0 via scenario B, rejected | evidence/controls/ |
| Untouched workspace | 0.0 all criteria | verified in every calibration round |


## Limitations

**Trial counts.** Opus: 0 passes in 4 post-escalation trials across two
environments (3 containered, 1 native-CLI local). GPT: 1 pass at the v2
intermediate bar, 2 failures at v3 and shipped. Blind auditor: n=1 per task
version.

**Single-blind m17.** m17 was validated blind by exactly one solver (the
auditor, the strongest model tested). The n-1 slack in the threshold means a
solver missing only m17 still passes.

**Wall-clock runtime.** Runtimes are short (6-12 minutes) because frontier
models are fast. The long-horizon claim is structural: four dependent
deliverables, hypothesis formation from conflicting evidence, and a
held-out verification component with no solve-time feedback. Not temporal.

**Synthetic data.** The data is uniform and synthetic by design, for
unambiguous grading. Ragged, noisy data is a future difficulty knob, not a
current feature.

**3-of-4 criterion pattern.** Both models pass 3 of 4 criteria. The
conjunctive-contract argument for why that constitutes a task failure is
given in the grader-design section, and the per-criterion breakdown is
always reported alongside the overall score.

**Model access.** Routed via OpenRouter (billing route only). The harnesses
are the real Claude Code CLI and Codex CLI. Model IDs are pinned in run
configs.

**Local trial.** During an API-credits outage, one Opus trial ran on the
native CLI locally rather than in a container. The full transcript is
shipped. Containered runs remain the headline evidence.


## Costs

Total spend across all model runs and smoke tests: $13.55 of a $35 budget.

Opus trials ran at roughly $2.3-2.5 each. GPT trials at roughly $3-3.5
each. Prompt-cache hit rate was ~96% in containered Claude Code runs.


## Evidence

The evidence folder is organized into three sections. Every load-bearing
claim in this report maps to a file. The complete mapping is in
`evidence/INDEX.md`.

### evidence/headline/

Shipped-grader runs. Per-mutant kill matrices in `*/verifier/grader_detail.json`.

| Claim | Path |
|-------|------|
| Oracle passes 1.0, twice | headline/oracle-run-1/, headline/oracle-run-2/ |
| Blind auditor passes 1.0, 16/16, zero false alarms | headline/blind-solver/ (transcript, reward, workspace, INTEGRITY.md) |
| GPT-5.5-high fails 0.70, 13/16, survivors m11/m14/m17 | headline/gpt-5.5-high/ |
| Opus 4.7 fails 0.70, 11/16, survivors m10/m11/m13/m14/m17 | headline/opus-4.7/ |

### evidence/supporting/

Calibration-history runs.

| Claim | Path |
|-------|------|
| Opus failed in a second environment (native CLI, local) | supporting/opus-local-native/ |
| Opus failed at v3 bar, 12/18 | supporting/opus-trial3-18bar/ |
| GPT failed at v3 bar, 14/18 | supporting/gpt-18bar/ |
| Opus failed at v2 bar, 13/15 | supporting/opus-15bar/ |
| GPT passed at v2 bar, 14/15, 1.0 | supporting/gpt-15bar-pass/ |
| Opus passed v1 task (triggered escalation) | supporting/opus-round1-pass/ |

### evidence/controls/

| Claim | Path |
|-------|------|
| Lazy suite: 2/16, every escalation mutant survives | controls/mutant-proofs-and-lazy-suite.txt |
| Source-grepping cheat suite capped at 0.5 | controls/anti-grep-demo.txt |
| All 18 mutants provably killable; m16/m18 excluded by blind-reachability | controls/ + tests/mutants/MUTANTS.md |
