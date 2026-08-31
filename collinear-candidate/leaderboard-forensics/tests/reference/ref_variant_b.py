"""Correct scorer, variant B. Behaviorally identical to ref_scorer.py but
aggressively rewritten at the text level: the alias table is packed data,
the rounding-mode constant never appears as a literal token, and internal
names share nothing with the reference. A suite that greps the source of
the implementation under test (instead of testing behavior) will judge
this CORRECT implementation broken and trip the false-alarm cap.
Stdlib only."""

import decimal

_W = dict(zip(
    ("account_access", "billing", "technical_error", "product_defect",
     "refunds", "shipping", "returns", "data_privacy", "subscription",
     "warranty", "feature_request", "general_inquiry"),
    (3, 3, 3, 3, 2, 2, 2, 2, 2, 1, 1, 1),
))

_PACKED = (
    "login issue>account_access|sign in>account_access|signin>account_access|"
    "locked out>account_access|payment>billing|billing issue>billing|"
    "invoice>billing|overcharge>billing|refund>refunds|money back>refunds|"
    "bug>technical_error|crash>technical_error|error>technical_error|"
    "site down>technical_error|defect>product_defect|"
    "broken item>product_defect|faulty>product_defect|delivery>shipping|"
    "package>shipping|tracking>shipping|return>returns|exchange>returns|"
    "privacy>data_privacy|gdpr request>data_privacy|"
    "delete my data>data_privacy|cancel subscription>subscription|"
    "upgrade plan>subscription|downgrade>subscription|guarantee>warranty|"
    "suggestion>feature_request|feature idea>feature_request|"
    "question>general_inquiry|other>general_inquiry|"
    "account access>account_access|technical error>technical_error|"
    "product defect>product_defect|data privacy>data_privacy|"
    "feature request>feature_request|general inquiry>general_inquiry"
)
_MAP = dict(pair.split(">") for pair in _PACKED.split("|"))

_MODE = getattr(decimal, "ROUND_HALF_" + "UP")
_GRID = decimal.Decimal("0.0001")


def _fold(raw):
    stage = raw.replace("_", " ").replace("-", " ")
    stage = " ".join(stage.lower().split())
    return _MAP.get(stage, stage)


def _snap(x):
    return float(decimal.Decimal(str(x)).quantize(_GRID, rounding=_MODE))


def score_model(gold, predictions, weights):
    picked = {}
    for item in predictions:
        ident = item["example_id"]
        if ident in gold and ident not in picked:
            picked[ident] = item["label"]

    box = {c: [0, 0, 0] for c in weights}  # tp, fp, fn
    for ident, truth in gold.items():
        final = _fold(picked[ident]) if ident in picked else None
        usable = final is not None and final in _W
        if usable and final == truth:
            box[truth][0] += 1
        elif usable:
            if final in box:
                box[final][1] += 1
            box[truth][2] += 1
        else:
            box[truth][2] += 1

    per_category = {}
    for cat in weights:
        tp, fp, fn = box[cat]
        d = 2 * tp + fp + fn
        per_category[cat] = {"tp": tp, "fp": fp, "fn": fn,
                             "f1": (2 * tp / d) if d else 0.0}

    seen_cats = set(gold.values())
    top = sum(weights[c] * per_category[c]["f1"] for c in weights if c in seen_cats)
    bot = sum(weights[c] for c in weights if c in seen_cats)
    return {"per_category": per_category,
            "overall": _snap(top / bot) if bot else 0.0}


def rank_models(overall_scores):
    order = sorted(overall_scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [name for name, _ in order]
