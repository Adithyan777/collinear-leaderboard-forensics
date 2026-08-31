"""mutant_13: violates SPEC 7.1 -- rounds per-category f1 values to 4dp (SPEC: f1 unrounded).
Killing input: refunds f1 = 2/3 reported as 0.6667 instead of 0.6666...
Generated from ref_scorer.py by dev/make_mutants.py."""

"""(mutated) implementation of
workspace/docs/SPEC.md. The verifier trusts THIS file, never the agent's
pipeline/scorer.py. Clause numbers in comments refer to SPEC sections.

Stdlib only. Deterministic.
"""

from decimal import Decimal, ROUND_HALF_UP

TAXONOMY_WEIGHTS = {
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


def normalize_label(raw):
    """SPEC 2.1-2.3. Returns the final label string (may be non-canonical)."""
    s = raw.replace("_", " ").replace("-", " ")   # 2.2 (before collapsing)
    s = " ".join(s.lower().split())               # 2.1 lowercase/strip/collapse
    return ALIASES.get(s, s)                      # 2.3 exact, at most once


def round_overall(x):
    """SPEC 7.1: ROUND_HALF_UP to 4 decimal places."""
    return float(Decimal(str(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def score_model(gold, predictions, weights):
    """SPEC API (section 10)."""
    # 3.3: first occurrence wins, in list order.
    seen = {}
    for row in predictions:
        eid = row["example_id"]
        if eid not in gold:
            continue  # 3.4: unknown ids contribute nothing
        if eid in seen:
            continue  # 3.3: later duplicates ignored
        seen[eid] = row["label"]

    counts = {c: {"tp": 0, "fp": 0, "fn": 0} for c in weights}
    for eid, gold_label in gold.items():
        if eid in seen:
            final = normalize_label(seen[eid])
            valid = final in TAXONOMY_WEIGHTS  # 3.1
        else:
            valid = False  # 3.2: missing prediction is INVALID
            final = None
        if valid and final == gold_label:
            counts[gold_label]["tp"] += 1  # 4.1
        elif valid:
            if final in counts:
                counts[final]["fp"] += 1   # 4.1 FP for predicted category
            counts[gold_label]["fn"] += 1  # 4.1 FN for gold category
        else:
            counts[gold_label]["fn"] += 1  # 4.1 INVALID: FN only, never FP

    per_category = {}
    for cat in weights:
        c = counts[cat]
        denom = 2 * c["tp"] + c["fp"] + c["fn"]
        f1 = (2 * c["tp"] / denom) if denom else 0.0  # 5.1
        per_category[cat] = {"tp": c["tp"], "fp": c["fp"], "fn": c["fn"], "f1": round(f1, 4)}

    gold_present = {g for g in gold.values()}
    num = sum(weights[c] * per_category[c]["f1"] for c in weights if c in gold_present)
    den = sum(weights[c] for c in weights if c in gold_present)  # 6.1/6.2
    overall = round_overall(num / den) if den else 0.0
    return {"per_category": per_category, "overall": overall}


def rank_models(overall_scores):
    """SPEC 8.1: descending score, ascending name on ties."""
    return [m for m, _ in sorted(overall_scores.items(), key=lambda kv: (-kv[1], kv[0]))]
