# Mutants: one SPEC-clause violation each

Graded set: 16 mutants (see below). Verifier threshold:
kills >= 15 of 16 (n-1). The agent instruction says the
suite should fail **every** broken implementation, so n-1 is one miss of
leniency in the agent's favor. Note the slack (1) is >= the number of
single-blind-validation mutants (1: mutant_17), so a blind solver missing
only the thinnest-validated mutant still passes.

Blind-reachability rule: every GRADED mutant must have been killed at
least once by a solver with no knowledge of the mutants (cf. SWE-bench
Verified's post-validation instance removal and METR's blind-completion
task standard). Blind-kill counts below come from the archived per-run
kill matrices (runs/*/verifier/grader_detail.json).

## Graded mutants

| Mutant | Clause | Violation | Killing input | Blind kills |
|--------|--------|-----------|---------------|-------------|
| mutant_01 | SPEC 2.1 | skips lowercasing (case-sensitive matching) | predict "Billing" vs gold billing -> INVALID instead of TP | 8/8 (all blind suites) |
| mutant_02 | SPEC 2.2 | does not map underscores/hyphens to spaces | predict "billing_issue" -> stays "billing_issue", misses the alias | 8/8 (all blind suites) |
| mutant_03 | SPEC 2.3 | skips the alias table entirely | predict "payment" vs gold billing -> INVALID instead of TP | 8/8 (all blind suites) |
| mutant_04 | SPEC 3.1/4.1 | invalid predictions also counted as FP against the gold category | gold billing x2, one junk + one correct -> billing fp=1 shifts f1 (2/3 -> 0.5) | 8/8 (all blind suites) |
| mutant_05 | SPEC 3.2 | missing predictions silently skipped instead of counted as FN | omit one gold example from predictions -> its category F1 too high | 8/8 (all blind suites) |
| mutant_06 | SPEC 3.3 | last duplicate occurrence wins instead of first | same example twice: correct then wrong -> mutant scores the wrong one | 8/8 (all blind suites) |
| mutant_07 | SPEC 3.4 | rows with unknown example_ids counted as FPs | stray row with unknown id and valid label -> spurious FP | 8/8 (all blind suites) |
| mutant_08 | SPEC 5.1 | uses recall instead of F1 | any category with FP>0 or asymmetric FP/FN scores differently | 8/8 (all blind suites) |
| mutant_09 | SPEC 6.1/6.2 | aggregates over ALL weighted categories, not just gold-present | full weights + few gold categories -> denominator inflated | 8/8 (all blind suites) |
| mutant_10 | SPEC 7.1 | banker's rounding (built-in round) instead of ROUND_HALF_UP | overall landing on a .xxxx5 boundary rounds down instead of up | 5/8 (Opus R1, auditor v1, GPT x2, auditor v2) |
| mutant_11 | SPEC 3.3 | dedup keeps first VALID occurrence instead of first occurrence | duplicate pair invalid-then-valid: ref scores the invalid first row (FN); mutant rescues the valid second | 2/6 (Opus containered, auditor v2) |
| mutant_12 | SPEC 2.1 | collapses ASCII space runs only; other Unicode whitespace not treated as whitespace | "sign\u00a0in" (NBSP) or "sign\tin" fails to normalize -> INVALID instead of account_access | 6/6 (all facing suites) |
| mutant_13 | SPEC 7.1 | rounds per-category f1 values to 4dp (SPEC: f1 unrounded) | refunds f1 = 2/3 reported as 0.6667 instead of 0.6666... | 4/6 (Opus containered, GPT x2, auditor v2) |
| mutant_14 | SPEC 2.3 | startswith alias matching instead of exact whole-string | "payment issue" wrongly maps to billing; ref treats it as INVALID | 3/6 (GPT x2, auditor v2) |
| mutant_15 | SPEC 8.1 | ranking ties broken by model name descending instead of ascending | two models tied on rounded score sort in reverse name order | 6/6 (all facing suites) |
| mutant_17 | SPEC 6.2 | rounds intermediate per-category F1s to 4dp BEFORE the weighted aggregation (SPEC: all intermediate values stay unrounded); reported f1 stays unrounded, unlike mutant_13 | billing f1=2/3 and refunds f1=0.5 with equal weights: true overall 7/12 -> 0.5833; mutant aggregates (0.6667+0.5)/2 = 0.58335 -> 0.5834 | 1/4 (auditor v2 only) |

## Excluded by blind-reachability validation (present on disk, NOT graded)

| Mutant | Clause | Violation | Killing input | Blind kills |
|--------|--------|-----------|---------------|-------------|
| mutant_16 | SPEC 7.1 | always rounds the overall UP (ceiling at 4dp) instead of ROUND_HALF_UP | the SPEC 9 example 0.86665 -> 0.8667 PASSES this mutant; killing needs an overall that must round DOWN, e.g. overall = 1/3 -> 0.3333 (ceiling gives 0.3334) | 0/4 |
| mutant_18 | SPEC 6.1 | judges validity against the passed weights keys instead of the canonical 12-label taxonomy (SPEC: validity is always judged against the taxonomy, regardless of weights) | weights {"billing": 1, "widget": 1} + prediction "widget" for gold billing: ref treats "widget" as INVALID (FN only, widget fp=0); mutant treats it as valid -> widget fp=1 | 0/4 |

Both excluded mutants were designed in the expert-review round,
implemented, and verified oracle-killable -- but across every blind suite
evaluated against them (5 blind attempts at the task) no solver thought of
the killing scenario. They are retained, ungraded, as documented future
difficulty knobs. The rule cuts symmetrically: mutant_17 hurt the models
exactly as much as these two, and it stays graded because one blind
solver killed it; 16/18 would have widened the failure gap and were
removed anyway. Selection conditioned on solvability evidence, not on
which model passes.
