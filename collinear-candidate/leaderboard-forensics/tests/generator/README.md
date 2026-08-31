# generator/ — the seeded world builder

Every file the agent sees was produced by this generator. It is
deterministic: the same seed gives a byte-identical workspace, which is the
provenance guarantee (100% synthetic, nothing copied from anywhere).

- `gen_all.py` — entry point; builds the complete committed workspace from
  `AGENT_SEED`, with built-in assertions
- `genworld.py` — generates the gold labels, model predictions, and shards
- `corrupt.py` — replays the crash and buggy resume through the real
  pipeline code, producing the corrupted August artifacts (surplus shard_07
  rows, missing shard_08 rows) exactly as the team's run would have
- `dress.py` — writes the surrounding world: logs, the support ticket,
  README, RUNBOOK, CHANGELOG, and the July archive
- `seeds.py` — the seed constants; the grader uses a different seed to build
  the held-out world for the root-cause check
