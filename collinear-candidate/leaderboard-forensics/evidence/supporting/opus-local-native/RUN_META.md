# Round 2 (local): Claude Opus 4.7, native Claude Code harness, escalated task
- Date: 2026-08-30, ~10:24 PM IST; duration ~4m22s (agent-reported)
- Harness: real Claude Code CLI, interactive session, --model claude-opus-4-7,
  billed to candidate's own Claude plan (OpenRouter credits were 402-blocked)
- Environment: sealed sandbox copy of environment/workspace + instruction.md
  (paths rewritten), venv python 3.12.8 + pytest 8.4.1 on PATH (mirrors container)
- Prompt: instruction.md verbatim, single message, no steering, no interventions
- RESULT: overall 0.92 — FAILED (all-criteria bar): root_cause_fix 1.0,
  data_repair 1.0, report_accuracy 1.0, test_suite 0.7333 (11/15 mutants killed;
  threshold 14/15). Survivors: mutant_10 (§7.1 banker's overall rounding),
  mutant_11 (§3.3 first-valid-wins dedup), mutant_13 (§7.1 per-category f1
  rounded), mutant_14 (§2.3 substring alias). Zero false alarms.
- Integrity: session transcript grepped for forbidden paths — zero reads outside
  sandbox (only pytest banner showing venv path + /dev/null fragments).
- Model's own closing summary CLAIMED §7.1 and §3.3 coverage while both
  survived — self-authored-oracle failure mode, pre-registered.
- Caveats: local macOS env (not the pinned container), single trial, candidate's
  plan billing. Containered Harbor run remains the preferred headline evidence
  if credits return.
