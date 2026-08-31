"""Correct scorer, variant A. Behaviorally identical to ref_scorer.py but
textually rewritten (renamed internals, reordered logic). Used by the
mutation grader's round-0 so that suites asserting on source TEXT rather
than BEHAVIOR false-alarm on a correct implementation. Stdlib only."""

from decimal import Decimal, ROUND_HALF_UP

CANON = {
    "account_access": 3, "billing": 3, "technical_error": 3,
    "product_defect": 3, "refunds": 2, "shipping": 2, "returns": 2,
    "data_privacy": 2, "subscription": 2, "warranty": 1,
    "feature_request": 1, "general_inquiry": 1,
}

SYNONYMS = {
    "login issue": "account_access", "sign in": "account_access",
    "signin": "account_access", "locked out": "account_access",
    "payment": "billing", "billing issue": "billing", "invoice": "billing",
    "overcharge": "billing", "refund": "refunds", "money back": "refunds",
    "bug": "technical_error", "crash": "technical_error",
    "error": "technical_error", "site down": "technical_error",
    "defect": "product_defect", "broken item": "product_defect",
    "faulty": "product_defect", "delivery": "shipping",
    "package": "shipping", "tracking": "shipping", "return": "returns",
    "exchange": "returns", "privacy": "data_privacy",
    "gdpr request": "data_privacy", "delete my data": "data_privacy",
    "cancel subscription": "subscription", "upgrade plan": "subscription",
    "downgrade": "subscription", "guarantee": "warranty",
    "suggestion": "feature_request", "feature idea": "feature_request",
    "question": "general_inquiry", "other": "general_inquiry",
    "account access": "account_access", "technical error": "technical_error",
    "product defect": "product_defect", "data privacy": "data_privacy",
    "feature request": "feature_request", "general inquiry": "general_inquiry",
}


def _clean(raw):
    # 2.2 first (separators to spaces), then 2.1 (case/strip/collapse)
    text = raw.replace("_", " ").replace("-", " ")
    text = " ".join(text.lower().split())
    # 2.3: exact whole-string synonym lookup, applied at most once
    if text in SYNONYMS:
        return SYNONYMS[text]
    return text


def _round4(value):
    # 7.1
    q = Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return float(q)


def score_model(gold, predictions, weights):
    chosen = {}
    for entry in predictions:
        key = entry["example_id"]
        if key not in gold or key in chosen:
            continue  # 3.4 unknown ids inert; 3.3 first occurrence wins
        chosen[key] = entry["label"]

    tally = {}
    for cat in weights:
        tally[cat] = {"tp": 0, "fp": 0, "fn": 0}

    for key in gold:
        truth = gold[key]
        label = None
        ok = False
        if key in chosen:
            label = _clean(chosen[key])
            ok = label in CANON  # 3.1: canonical taxonomy decides validity
        if ok and label == truth:
            tally[truth]["tp"] += 1
        elif ok:
            if label in tally:
                tally[label]["fp"] += 1
            tally[truth]["fn"] += 1
        else:
            tally[truth]["fn"] += 1  # 3.2/4.1: INVALID or missing -> FN only

    per_category = {}
    for cat in weights:
        t = tally[cat]
        denom = 2 * t["tp"] + t["fp"] + t["fn"]
        f1 = (2 * t["tp"] / denom) if denom else 0.0
        per_category[cat] = {"tp": t["tp"], "fp": t["fp"], "fn": t["fn"], "f1": f1}

    present = set(gold.values())
    num = sum(weights[c] * per_category[c]["f1"] for c in weights if c in present)
    den = sum(weights[c] for c in weights if c in present)
    overall = _round4(num / den) if den else 0.0
    return {"per_category": per_category, "overall": overall}


def rank_models(overall_scores):
    return [name for name, _ in
            sorted(overall_scores.items(), key=lambda kv: (-kv[1], kv[0]))]
