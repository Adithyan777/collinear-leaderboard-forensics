# Blind-solver integrity check (reproducible)

The auditor agent received ONLY a sealed sandbox (instruction.md + a copy of
environment/workspace). This transcript is its complete session. To verify it
never accessed grader/mutant/oracle/design material, run the greps below against
auditor-session-transcript.jsonl in this directory — every count must be 0:

    for p in "tests/mutants" "mutant_1" "ref_scorer" "ref_variant" \
             "check_mutation" "MUTANTS" "build-log" "review-packet" \
             "expert-briefing" "solve.sh" "clause-map"; do
      echo "$p: $(grep -c "$p" auditor-session-transcript.jsonl)"
    done

Result at archive time: all zero. The effort nudge given to the auditor (quoted
in RUN_REPORT.md) named no scenarios, rounding directions, or weights tricks.
