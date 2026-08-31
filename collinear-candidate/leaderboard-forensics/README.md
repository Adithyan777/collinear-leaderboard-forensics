# leaderboard-forensics

A Harbor evaluation task that isolates adversarial self-validation: the ability
to write tests that could catch errors the solver did not already think of.
Both frontier models tested (Claude Opus 4.7, GPT-5.5) ace the forensics,
the pipeline fix, the data repair, and the report. Both fail the acceptance
suite, because the only feedback on its correctness is feedback the solver
manufactures for itself.


## The scenario

The agent joins the eval-platform team at Meridian Labs. The team runs a
monthly ticket-triage benchmark that scores 6 vendor models (cascade-2,
aurora-70b, bramble-x, foxtail-pro, dune-mini, ember-8x) on 3,996
gold-labeled support tickets spread across 12 shards. The scoring pipeline
reads ~24k prediction rows from JSONL files, writes results into SQLite,
and builds a leaderboard CSV.

The August scoring run crashed mid-shard (a disk I/O error during shard_08)
and was resumed. The resume logic in `pipeline/checkpoint.py::resume_plan`
has two bugs triggered by this crash:

1. It re-scores the already-committed previous shard (shard_07), producing
   1,998 surplus rows.
2. It marks the interrupted shard (shard_08) as completed without scoring it,
   leaving 1,998 rows missing.

Because each shard has the same number of rows per model, the surplus and
shortfall cancel in the total row count. Every model still has 3,996 rows.
The published leaderboard, the SQLite database, and RESULTS.md all agree
with each other. They are internally consistent but wrong. The corruption
inflated bramble-x from a correct 0.7817 (rank 3) to a published 0.8112
(rank 2).

A support ticket (TICKET-4127) reports the suspicious ranking. The ticket is
honest but wrong. Every fact in it is true and checkable: the dates, the code
change it references (an NBSP-handling edit in `normalize.py` dated
2026-08-12, the same day as the run), the score discrepancy it flags. Only
its conclusion is speculation. The normalize.py change is innocent.

Corrected leaderboard:

| Rank | Model | Overall |
|------|-------|---------|
| 1 | cascade-2 | 0.8356 |
| 2 | aurora-70b | 0.7964 |
| 3 | bramble-x | 0.7817 |
| 4 | foxtail-pro | 0.7208 |
| 5 | dune-mini | 0.6825 |
| 6 | ember-8x | 0.6330 |


## Agent deliverables

The instruction asks for four deliverables:

**1. Root-cause fix.** Fix the bug in the pipeline code. The CLI entry points
(`python -m pipeline.run_scoring`, `--resume`, `python -m pipeline.build_leaderboard`)
must keep working with unchanged interfaces. A run can be interrupted at any
point; re-running with `--resume` must converge to the same correct final
state (exactly one row per model per gold example).

**2. Repaired artifacts.** Rebuild the August `db/results.sqlite` and
`leaderboard.csv` from the raw prediction data per `docs/SPEC.md`. Exact
schemas are specified in the instruction.

**3. Findings report.** Write `report.json` with machine-checked fields:
shard anomalies (surplus_rows / missing_rows with exact counts), corrected
scores to 4 decimal places, corrected ranking.

**4. Acceptance tests.** Write a pytest suite against `docs/SPEC.md` that
checks a scorer implementation. The instruction states explicitly that the
suite will be run against multiple implementations, one correct and several
deliberately broken, and must pass the correct one and fail every broken one.
The SPEC has 14 numbered clauses covering normalization, alias resolution,
validity, duplicate/stray row handling, per-category F1, weighted
aggregation, ROUND_HALF_UP rounding, and ranking tie-breaks.


## Design rationale

Ground truth in this task exists in two forms: as raw evidence in the world
(recomputable data, readable logs, the SPEC), and as judgment in a hidden
verifier mounted only after the agent finishes. Deliverables 1 through 3
have queryable ground truth at solve time. Run the pipeline, count rows,
compare to the SPEC. Every model I tested aced all three in every run.

Deliverable 4 has no queryable ground truth. The broken implementations are
invisible until grading. The only feedback on the suite's quality is feedback
the solver creates. This is the capability seam the task targets.

The acceptance suite is graded by mutation testing because it isolates a
specific discipline: verifying work against a contract you cannot query, where
the only feedback is feedback you manufacture yourself. The instruction tells
the agent what will happen (its suite faces correct and broken
implementations) but not what the broken implementations are.

The task does not ask the agent to guess hidden secrets. Every graded mutant
breaks a numbered clause of `docs/SPEC.md`, which the agent can read the
whole time. What is measured is a working method: for each clause, ask how
someone could plausibly get it wrong, then pick a test input where the right
and wrong versions give different answers. The blind auditor scored 16/16
using only that method and the files in the workspace, knowing nothing about
the mutants -- proof the bar is reachable from the SPEC alone.

The misleading ticket is a wrong-but-honest anchor. It exists to test
whether the agent follows evidence rather than accepting a plausible
explanation.


## Verifier

`tests/grader/main.py` writes `reward.json` with 4 criteria. Overall is
1.0 only if all four pass.

**root_cause_fix:** The agent's fixed pipeline runs end-to-end on a held-out
corrupted world generated from a different seed. Two crash scenarios are
tested: (A) mid-write rollback, and (B) rows committed but shard not marked
done. A fix that only patches `resume_plan` without making writes idempotent
fails scenario B.

**data_repair:** The rebuilt database and leaderboard are compared against an
independent reference recompute of the August data.

**report_accuracy:** Schema validation plus tolerance comparison of reported
numbers.

**test_suite:** Mutation grading. The agent's suite runs against 3 correct
scorer implementations (the reference plus two behaviorally-identical but
textually-rewritten variants, as an anti-cheat against source-grepping
suites) and 16 graded broken scorers. The threshold is kills >= 15 (integer).
Any failure against any correct implementation caps the criterion at 0.5.
The test_suite component is binary: full weight if the suite passes the
threshold with zero false alarms, else 0. The instruction states a
conjunctive contract ("fail every broken one"), and averaging a categorical
miss into a fraction would launder a contract failure into a high score.
Raw kill counts are always recorded in `grader_detail.json`.

Controls: a lazy two-test suite scores 2/16. A demo source-grepping cheat
suite text-kills 14/16 mutants but false-alarms both rewritten correct
variants and is capped at 0.5. Shallow-fix control A (data repaired but bug
unfixed) is rejected with root_cause_fix 0. Shallow-fix control B
(resume_plan fixed but no idempotent writes) is rejected via scenario B.


## Provenance

100% synthetic. Every file in the task workspace was generated from a seeded
deterministic generator. Running the generator twice produces byte-identical
output. No external code, datasets, or benchmark content was used.

Task design was informed by my private analysis of 1,748 failed agent
trajectories (Claude Opus 4.7/4.6, GPT-5.2, Kimi K2.5, Gemini across three
different harnesses). That analysis identified verification-against-self-
authored-standards as the dominant cross-model failure mode.


## Environment

- Base image: digest-pinned `python:3.11-slim`
- Network: `network_mode: no-network`
- Agent timeout: 3600s
- Verifier timeout: 900s
- Resources: 2 CPUs, 4096 MB memory, 10240 MB storage

The documented runtime allowlist covers only agent-harness installation and
API egress. Task content requires zero network access. The verifier is fully
offline.

Agent-harness allowlist (Claude Code):
`deb.debian.org`, `security.debian.org`, `downloads.claude.ai`, `claude.ai`,
`storage.googleapis.com`, `openrouter.ai`

Agent-harness allowlist (Codex):
`deb.debian.org`, `security.debian.org`, `registry.npmjs.org`, `nodejs.org`,
`raw.githubusercontent.com`, `github.com`, `objects.githubusercontent.com`,
`openrouter.ai`

### Network policy

The task itself needs zero network. The workspace is self-contained and the
verifier runs fully offline. The allowlist exists for two harness concerns:
Harbor installs the agent CLI inside the container at setup time, and the
agent must reach its model API. The allowlist lives in the run-command
flags, not in `task.toml`; the task ships as strict no-network, and each
evaluator opts into exactly the egress their harness needs.

| Host | Purpose | Harness |
|------|---------|---------|
| `deb.debian.org`, `security.debian.org` | apt packages (Node.js runtime for both CLIs) | both |
| `downloads.claude.ai`, `claude.ai`, `storage.googleapis.com` | Claude Code bootstrap installer and release CDN | Claude Code |
| `registry.npmjs.org`, `nodejs.org` | npm install of Codex CLI and Node downloads | Codex |
| `raw.githubusercontent.com`, `github.com`, `objects.githubusercontent.com` | Node/nvm install scripts and GitHub release assets | Codex |
| `openrouter.ai` | model API | both |

Every host was discovered empirically. I started from pure no-network and
added only what each observed install failure required. Harbor enforces the
list with an egress-control sidecar; everything not listed is blocked.

Agent-phase egress does not threaten the task's integrity. There is nothing
to find online: the task is fully synthetic, no repository anywhere contains
this SPEC, these mutants, or any answer key (unlike tasks built on real
repositories, where the fix exists online). The answer key never coexists
with the network: `tests/` is mounted only after the agent's session ends.
Every shipped run's full transcript is in `evidence/`, showing workspace
work and API traffic only.

Honest caveat: hostname-level allowlisting is coarse.
`storage.googleapis.com` and `github.com` are large shared CDNs, so the
harness's needs grant broader surface than ideal. This is flake risk, not
integrity risk: an unreachable host fails a run as infrastructure error,
not task failure.

I considered baking Node and the agent CLIs into the task image (Harbor
supports this). I rejected it: the model-API host must stay open regardless,
so baking shrinks the allowlist but cannot close it; the task image defines
the world, not the examiner, so coupling it to two specific CLIs is wrong;
and version drift is fragile (the Codex adapter reinstalls when the version
does not match, silently reintroducing network needs).


## Reproduction

Setup (from the repository root; Docker must be running):

```
uv venv && uv pip install harbor==0.22.0
# or: python -m venv .venv && .venv/bin/pip install harbor==0.22.0
echo 'OPENROUTER_API_KEY=sk-or-...' > .env   # only needed for the model runs
```

All runs below were made with harbor 0.22.0. The oracle run needs no API
key and no network.

Oracle:

```
.venv/bin/harbor run -p <task-dir> -a oracle -o <jobs-dir> -q -y
```

Claude Code (Opus 4.7 via OpenRouter):

```
.venv/bin/harbor run -p collinear-candidate/leaderboard-forensics -a claude-code \
  -m "anthropic/claude-opus-4.7" --env-file .env \
  --allow-environment-host deb.debian.org --allow-environment-host security.debian.org \
  --allow-environment-host downloads.claude.ai --allow-environment-host claude.ai \
  --allow-environment-host storage.googleapis.com --allow-environment-host openrouter.ai \
  -o runs -q -y
```

Codex (GPT-5.5 via OpenRouter):

```
.venv/bin/harbor run -p collinear-candidate/leaderboard-forensics -a codex \
  -m "openai/gpt-5.5" --env-file .env \
  --ak reasoning_effort=high \
  --allow-environment-host deb.debian.org --allow-environment-host security.debian.org \
  --allow-environment-host registry.npmjs.org --allow-environment-host nodejs.org \
  --allow-environment-host raw.githubusercontent.com --allow-environment-host github.com \
  --allow-environment-host objects.githubusercontent.com --allow-environment-host openrouter.ai \
  -o runs -q -y
```


## Headline results

All runs physical. Shipped grader (16 graded mutants, kills >= 15, binary
test_suite readout).

| Solver | Kills | Overall | Runtime |
|--------|-------|---------|---------|
| Oracle | 16/16 | 1.0 (twice) | ~30s |
| Blind auditor (Fable agent, sealed sandbox) | 16/16 | 1.0 | -- |
| GPT-5.5-high (Codex) | 13/16 | 0.70 FAIL | 10m21s |
| Claude Opus 4.7 (Claude Code) | 11/16 | 0.70 FAIL | 7m31s |

Both models scored 1.0 on root_cause_fix, data_repair, and report_accuracy.
The failure is isolated entirely to the acceptance-suite criterion. Zero
false alarms from either model: their suites are never wrong about what they
assert, only silently incomplete.

Full run history and calibration details: [RUN_REPORT.md](RUN_REPORT.md).


## File layout

```
leaderboard-forensics/
  instruction.md          # what the agent sees
  task.toml               # Harbor task config
  environment/
    Dockerfile
    workspace/            # the corrupted world the agent works in
  solution/               # oracle solver
  tests/
    grader/               # verifier (main.py writes reward.json)
    reference/            # correct scorer + two anti-grep variants
    mutants/              # 16 graded + 2 excluded broken scorers
    generator/            # seeded deterministic world generator
  evidence/               # run artifacts, transcripts, controls
    INDEX.md              # maps every claim to a file
    headline/             # shipped-grader runs (oracle, models, blind solver)
    supporting/           # calibration history runs
    controls/             # lazy suite, anti-grep demo, shallow fixes
  README.md               # this file
  RUN_REPORT.md           # full run report with calibration history
```
