"""Seeded generator for the clean world: gold labels + model predictions.

Determinism rules: one random.Random(seed) per build, sorted iteration,
sort_keys JSON, no wall clock anywhere.
"""

import json
import random

N_EXAMPLES = 3996
SHARD_SIZE = 333
SHARDS = [f"shard_{i:02d}" for i in range(12)]

CATEGORIES = [
    "account_access", "billing", "technical_error", "product_defect",
    "refunds", "shipping", "returns", "data_privacy", "subscription",
    "warranty", "feature_request", "general_inquiry",
]

# plausible ticket-volume mix (sums to 1.0)
GOLD_MIX = {
    "billing": 0.16, "account_access": 0.14, "technical_error": 0.13,
    "shipping": 0.12, "refunds": 0.10, "returns": 0.08, "product_defect": 0.07,
    "subscription": 0.06, "data_privacy": 0.05, "general_inquiry": 0.04,
    "warranty": 0.03, "feature_request": 0.02,
}

ALIASES_REVERSE = {
    "account_access": ["login issue", "sign in", "signin", "locked out"],
    "billing": ["payment", "billing issue", "invoice", "overcharge"],
    "refunds": ["refund", "money back"],
    "technical_error": ["bug", "crash", "error", "site down"],
    "product_defect": ["defect", "broken item", "faulty"],
    "shipping": ["delivery", "package", "tracking"],
    "returns": ["return", "exchange"],
    "data_privacy": ["privacy", "gdpr request", "delete my data"],
    "subscription": ["cancel subscription", "upgrade plan", "downgrade"],
    "warranty": ["guarantee"],
    "feature_request": ["suggestion", "feature idea"],
    "general_inquiry": ["question", "other"],
}

JUNK_LABELS = ["unsure", "spam?", "misc", "n/a", "escalate", "customer angry", "??"]

# model -> base accuracy for the August run
MODELS_AUG = {
    "aurora-70b": 0.82,
    "bramble-x": 0.805,
    "cascade-2": 0.86,
    "dune-mini": 0.70,
    "ember-8x": 0.66,
    "foxtail-pro": 0.75,
}

# July run (previous month): bramble-x notably weaker, no hot shard.
MODELS_JUL = {
    "aurora-70b": 0.78,
    "bramble-x": 0.72,
    "cascade-2": 0.845,
    "dune-mini": 0.71,
    "ember-8x": 0.67,
    "foxtail-pro": 0.755,
}

HOT_MODEL = "bramble-x"
HOT_BOOST = 0.15   # bramble's strong shard (the one the buggy resume re-scores)
COLD_DROP = 0.18   # bramble's weak shard (the one the buggy resume skips)
JITTER = 0.03      # mild per-(model, shard) variation for everyone


def example_id(i):
    return f"tkt-{i:05d}"


def shard_of_index(i):
    return SHARDS[i // SHARD_SIZE]


def make_gold(rng):
    cats = sorted(GOLD_MIX)
    weights = [GOLD_MIX[c] for c in cats]
    return {example_id(i): rng.choices(cats, weights=weights)[0]
            for i in range(N_EXAMPLES)}


def _variant(rng, label):
    """Formatting variants that are still correct after normalization."""
    v = rng.random()
    if v < 0.35 and ALIASES_REVERSE.get(label):
        s = rng.choice(ALIASES_REVERSE[label])
    else:
        s = label
    f = rng.random()
    if f < 0.12:
        s = s.replace(" ", "_") if " " in s else s.upper()
    elif f < 0.22:
        s = s.title()
    elif f < 0.30:
        s = f"  {s} "
    elif f < 0.36 and " " in s:
        s = s.replace(" ", "-")
    return s


def make_predictions(rng, gold, models, hot_shard=None, cold_shard=None):
    """Returns {shard: [row, ...]} with rows in deterministic emit order."""
    jitter = {(m, s): rng.uniform(-JITTER, JITTER)
              for m in sorted(models) for s in SHARDS}
    shard_rows = {s: [] for s in SHARDS}
    for i in range(N_EXAMPLES):
        eid = example_id(i)
        shard = shard_of_index(i)
        gold_label = gold[eid]
        for model in sorted(models):
            q = models[model] + jitter[(model, shard)]
            if model == HOT_MODEL:
                if hot_shard is not None and shard == hot_shard:
                    q = models[model] + HOT_BOOST
                elif cold_shard is not None and shard == cold_shard:
                    q = models[model] - COLD_DROP
            q = min(0.98, max(0.05, q))
            e = rng.random()
            if e < 0.018:
                continue  # missing prediction for this model
            if rng.random() < q:
                intended = gold_label
            else:
                others = [c for c in CATEGORIES if c != gold_label]
                intended = rng.choice(others)
            if rng.random() < 0.012:
                raw = rng.choice(JUNK_LABELS)  # invalid after normalization
            else:
                raw = _variant(rng, intended)
            shard_rows[shard].append(
                {"example_id": eid, "model": model, "label": raw}
            )
            if rng.random() < 0.006:  # duplicate row; first occurrence wins
                shard_rows[shard].append(
                    {"example_id": eid, "model": model,
                     "label": rng.choice(JUNK_LABELS + [raw])}
                )
    # a few stray rows with ids outside the gold set (SPEC 3.4)
    for k in range(6):
        s = rng.choice(SHARDS)
        shard_rows[s].append(
            {"example_id": f"tkt-9{k:04d}", "model": rng.choice(sorted(models)),
             "label": rng.choice(CATEGORIES)}
        )
    return shard_rows


def write_world(dest, gold, shard_rows):
    (dest / "data" / "gold").mkdir(parents=True, exist_ok=True)
    (dest / "data" / "predictions").mkdir(parents=True, exist_ok=True)
    with open(dest / "data" / "gold" / "gold_labels.jsonl", "w", encoding="utf-8") as f:
        for eid in sorted(gold):
            f.write(json.dumps({"example_id": eid, "label": gold[eid]},
                               sort_keys=True) + "\n")
    for shard in SHARDS:
        with open(dest / "data" / "predictions" / f"{shard}.jsonl", "w",
                  encoding="utf-8") as f:
            for row in shard_rows[shard]:
                f.write(json.dumps(row, sort_keys=True) + "\n")


def build_clean_world(dest, seed, models, hot_shard=None, cold_shard=None):
    rng = random.Random(seed)
    gold = make_gold(rng)
    shard_rows = make_predictions(rng, gold, models, hot_shard=hot_shard,
                                  cold_shard=cold_shard)
    # structural guarantee (stated in instruction.md): every model appears in
    # every shard file
    for shard in SHARDS:
        present = {r["model"] for r in shard_rows[shard]}
        missing = set(models) - present
        assert not missing, f"{shard} missing models {missing} (seed {seed})"
    write_world(dest, gold, shard_rows)
    return gold, shard_rows


def crash_index(seed):
    """Which shard the scoring run dies in (needs >=2 before, >=1 after)."""
    return random.Random(seed * 31 + 7).randrange(3, 11)
