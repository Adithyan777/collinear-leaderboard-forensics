"""Benchmark configuration. Category weights and aliases mirror docs/SPEC.md;
the SPEC is authoritative if they ever drift."""

from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

GOLD_PATH = WORKSPACE / "data" / "gold" / "gold_labels.jsonl"
PREDICTIONS_DIR = WORKSPACE / "data" / "predictions"
DB_PATH = WORKSPACE / "db" / "results.sqlite"
CHECKPOINT_PATH = WORKSPACE / "state" / "checkpoint.json"
LEADERBOARD_PATH = WORKSPACE / "leaderboard.csv"
RESULTS_MD_PATH = WORKSPACE / "RESULTS.md"

SHARDS = [f"shard_{i:02d}" for i in range(12)]
SHARD_SIZE = 333  # tkt-00000..tkt-03995, contiguous ranges


def shard_of(example_id: str) -> str:
    idx = int(example_id.split("-")[1])
    return SHARDS[idx // SHARD_SIZE]


CATEGORY_WEIGHTS = {
    "account_access": 3,
    "billing": 3,
    "technical_error": 3,
    "product_defect": 3,
    "refunds": 2,
    "shipping": 2,
    "returns": 2,
    "data_privacy": 2,
    "subscription": 2,
    "warranty": 1,
    "feature_request": 1,
    "general_inquiry": 1,
}

ALIASES = {
    "login issue": "account_access",
    "sign in": "account_access",
    "signin": "account_access",
    "locked out": "account_access",
    "payment": "billing",
    "billing issue": "billing",
    "invoice": "billing",
    "overcharge": "billing",
    "refund": "refunds",
    "money back": "refunds",
    "bug": "technical_error",
    "crash": "technical_error",
    "error": "technical_error",
    "site down": "technical_error",
    "defect": "product_defect",
    "broken item": "product_defect",
    "faulty": "product_defect",
    "delivery": "shipping",
    "package": "shipping",
    "tracking": "shipping",
    "return": "returns",
    "exchange": "returns",
    "privacy": "data_privacy",
    "gdpr request": "data_privacy",
    "delete my data": "data_privacy",
    "cancel subscription": "subscription",
    "upgrade plan": "subscription",
    "downgrade": "subscription",
    "guarantee": "warranty",
    "suggestion": "feature_request",
    "feature idea": "feature_request",
    "question": "general_inquiry",
    "other": "general_inquiry",
    "account access": "account_access",
    "technical error": "technical_error",
    "product defect": "product_defect",
    "data privacy": "data_privacy",
    "feature request": "feature_request",
    "general inquiry": "general_inquiry",
}
