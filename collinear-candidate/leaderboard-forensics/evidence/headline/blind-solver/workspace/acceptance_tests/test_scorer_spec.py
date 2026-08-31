"""Acceptance tests for the ticket-triage scorer against docs/SPEC.md (v2.3).

Contract under test:
    from scorer_under_test import score_model, rank_models

Every assertion here is behavior the SPEC explicitly requires (section
references inline). Only the standard library and pytest are used.
"""

from pytest import approx

from scorer_under_test import score_model, rank_models

# Canonical taxonomy weights, SPEC section 1.
WEIGHTS = {
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


def preds(*pairs):
    return [{"example_id": e, "label": l} for e, l in pairs]


def cat(result, name):
    return result["per_category"][name]


def total_fp(result):
    return sum(v["fp"] for v in result["per_category"].values())


# ---------------------------------------------------------------------------
# SPEC section 9: the worked end-to-end example is normative.
# ---------------------------------------------------------------------------

def worked_example_result():
    gold = {"e1": "billing", "e2": "billing", "e3": "refunds", "e4": "refunds"}
    p = preds(
        ("e1", " Billing "),      # 2.1: strip + lowercase -> billing (TP)
        ("e2", "payment"),         # 2.3: alias -> billing (TP)
        ("e3", "refund"),          # 2.3: alias -> refunds (TP)
        ("e4", "shipping issue"),  # 3.1: not taxonomy, not alias -> INVALID
    )
    return score_model(gold, p, WEIGHTS)


def test_worked_example_overall():
    # overall = (3*1.0 + 2*(2/3)) / 5 = 13/15 = 0.8666..., ROUND_HALF_UP -> 0.8667
    assert worked_example_result()["overall"] == approx(0.8667, abs=1e-9)


def test_worked_example_counts():
    r = worked_example_result()
    b, rf = cat(r, "billing"), cat(r, "refunds")
    assert (b["tp"], b["fp"], b["fn"]) == (2, 0, 0)
    assert (rf["tp"], rf["fp"], rf["fn"]) == (1, 0, 1)


def test_worked_example_per_category_f1_unrounded():
    # SPEC 7.1: per-category f1 is NOT rounded; refunds f1 is exactly 2/3.
    r = worked_example_result()
    assert cat(r, "billing")["f1"] == approx(1.0, abs=1e-12)
    assert cat(r, "refunds")["f1"] == approx(2.0 / 3.0, abs=1e-12)


# ---------------------------------------------------------------------------
# SPEC section 2: normalization of predicted labels.
# ---------------------------------------------------------------------------

def test_alias_mapping_applies():
    # SPEC 2.3 + alias table.
    gold = {"e1": "billing", "e2": "refunds", "e3": "technical_error",
            "e4": "general_inquiry", "e5": "account_access"}
    p = preds(("e1", "invoice"), ("e2", "money back"), ("e3", "site down"),
              ("e4", "other"), ("e5", "locked out"))
    r = score_model(gold, p, WEIGHTS)
    for c in ("billing", "refunds", "technical_error", "general_inquiry",
              "account_access"):
        assert cat(r, c)["tp"] == 1, c
    assert r["overall"] == approx(1.0, abs=1e-9)


def test_case_separator_and_whitespace_normalization():
    # SPEC 2.1-2.3: lowercase, strip, collapse unicode whitespace (U+00A0
    # counts), _ and - become spaces before collapsing, then alias.
    gold = {"e1": "account_access", "e2": "billing", "e3": "technical_error",
            "e4": "account_access", "e5": "billing"}
    p = preds(
        ("e1", "Sign-In"),               # 2.2 example: -> "sign in" -> alias
        ("e2", "billing__issue"),        # 2.2 example: -> "billing issue" -> alias
        ("e3", "Technical-Error"),       # -> "technical error" -> alias
        ("e4", "LOCKED\u00a0\u00a0OUT"),  # U+00A0 whitespace; run collapses
        ("e5", "  Billing\t"),           # strip + lowercase, canonical
    )
    r = score_model(gold, p, WEIGHTS)
    assert cat(r, "account_access")["tp"] == 2
    assert cat(r, "billing")["tp"] == 2
    assert cat(r, "technical_error")["tp"] == 1
    assert r["overall"] == approx(1.0, abs=1e-9)


def test_canonical_labels_pass_through():
    # SPEC 2.3: canonical labels not in the alias table pass through unchanged.
    gold = {"e1": "billing", "e2": "returns", "e3": "refunds"}
    p = preds(("e1", "billing"), ("e2", "returns"), ("e3", "refunds"))
    r = score_model(gold, p, WEIGHTS)
    assert cat(r, "billing")["tp"] == 1
    assert cat(r, "returns")["tp"] == 1
    assert cat(r, "refunds")["tp"] == 1
    assert r["overall"] == approx(1.0, abs=1e-9)


def test_alias_match_is_whole_string_only():
    # SPEC 2.3: exact whole-string match; "billing issue please" contains an
    # alias but is not one, so the prediction is INVALID (3.1) -> FN only.
    gold = {"e1": "billing"}
    r = score_model(gold, preds(("e1", "billing issue please")), WEIGHTS)
    b = cat(r, "billing")
    assert (b["tp"], b["fp"], b["fn"]) == (0, 0, 1)
    assert b["f1"] == approx(0.0, abs=1e-12)
    assert total_fp(r) == 0
    assert r["overall"] == approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# SPEC section 3: validity and row handling.
# ---------------------------------------------------------------------------

def test_invalid_prediction_is_fn_only_never_fp():
    # SPEC 3.1 + 4.1: invalid prediction -> FN for the gold category, no FP
    # anywhere.
    gold = {"e1": "refunds", "e2": "refunds"}
    p = preds(("e1", "refund"), ("e2", "totally not a label"))
    r = score_model(gold, p, WEIGHTS)
    rf = cat(r, "refunds")
    assert (rf["tp"], rf["fn"]) == (1, 1)
    assert total_fp(r) == 0
    # overall = f1(refunds) = 2/(2+0+1) = 2/3 -> 0.6667
    assert r["overall"] == approx(0.6667, abs=1e-9)


def test_missing_prediction_is_fn():
    # SPEC 3.2 + 4.1: gold example with no prediction row -> INVALID -> FN.
    gold = {"e1": "billing", "e2": "billing"}
    r = score_model(gold, preds(("e1", "billing")), WEIGHTS)
    b = cat(r, "billing")
    assert (b["tp"], b["fp"], b["fn"]) == (1, 0, 1)
    assert r["overall"] == approx(0.6667, abs=1e-9)


def test_duplicate_example_first_occurrence_wins():
    # SPEC 3.3 and micro-example (a): first row in list order wins.
    gold = {"e1": "billing"}
    r = score_model(gold, preds(("e1", "billing"), ("e1", "refunds")), WEIGHTS)
    assert cat(r, "billing")["tp"] == 1
    assert total_fp(r) == 0
    # Reversed order: the refunds row wins -> FP(refunds), FN(billing).
    r2 = score_model(gold, preds(("e1", "refunds"), ("e1", "billing")), WEIGHTS)
    assert cat(r2, "billing") ["fn"] == 1
    assert cat(r2, "billing")["tp"] == 0
    assert cat(r2, "refunds")["fp"] == 1


def test_duplicate_first_wins_even_when_first_is_invalid():
    # SPEC 3.3 makes no exception for invalid first occurrences.
    gold = {"e1": "billing"}
    r = score_model(gold, preds(("e1", "???"), ("e1", "billing")), WEIGHTS)
    b = cat(r, "billing")
    assert (b["tp"], b["fp"], b["fn"]) == (0, 0, 1)
    assert total_fp(r) == 0


def test_stray_example_ids_are_ignored_entirely():
    # SPEC 3.4: rows whose example_id is not in gold contribute nothing.
    gold = {"e1": "billing", "e2": "refunds"}
    clean = preds(("e1", "billing"), ("e2", "shipping"))
    noisy = preds(("zzz", "billing"), ("e1", "billing"), ("nope", "junk"),
                  ("e2", "shipping"), ("ghost", "refunds"))
    r_clean = score_model(gold, clean, WEIGHTS)
    r_noisy = score_model(gold, noisy, WEIGHTS)
    assert r_noisy["overall"] == approx(r_clean["overall"], abs=1e-12)
    for c in WEIGHTS:
        for k in ("tp", "fp", "fn"):
            assert cat(r_noisy, c)[k] == cat(r_clean, c)[k], (c, k)


# ---------------------------------------------------------------------------
# SPEC section 4: counting a wrong-but-valid prediction.
# ---------------------------------------------------------------------------

def test_wrong_valid_prediction_counts_fp_and_fn():
    # SPEC 4.1: valid prediction != gold -> FP(predicted) AND FN(gold).
    gold = {"e1": "billing", "e2": "refunds"}
    p = preds(("e1", "refund"), ("e2", "refunds"))  # e1 aliased to refunds
    r = score_model(gold, p, WEIGHTS)
    assert cat(r, "billing") ["fn"] == 1
    assert cat(r, "billing")["tp"] == 0
    rf = cat(r, "refunds")
    assert (rf["tp"], rf["fp"], rf["fn"]) == (1, 1, 0)
    # f1: billing = 0, refunds = 2/(2+1+0) = 2/3;
    # overall = (3*0 + 2*(2/3)) / 5 = 4/15 = 0.2666... -> 0.2667
    assert r["overall"] == approx(0.2667, abs=1e-9)


# ---------------------------------------------------------------------------
# SPEC sections 5-6: F1, reporting universe, weighted aggregation.
# ---------------------------------------------------------------------------

def test_zero_denominator_f1_is_zero_and_all_categories_reported():
    # SPEC 5.1 + 6.1: every weights category appears in per_category, unseen
    # ones as tp=0, fp=0, fn=0, f1=0.0; zero denominator -> f1 = 0.0.
    gold = {"e1": "billing"}
    r = score_model(gold, preds(("e1", "billing")), WEIGHTS)
    for c in WEIGHTS:
        assert c in r["per_category"], c
    for c in WEIGHTS:
        if c == "billing":
            continue
        k = cat(r, c)
        assert (k["tp"], k["fp"], k["fn"]) == (0, 0, 0), c
        assert k["f1"] == approx(0.0, abs=1e-12), c


def test_overall_excludes_gold_absent_categories():
    # SPEC 6.1/6.2: only gold-present categories enter the aggregate. With a
    # perfect score on the single gold-present category, overall is 1.0 even
    # though 11 weighted categories sit at f1 = 0.
    gold = {"e1": "billing", "e2": "billing"}
    r = score_model(gold, preds(("e1", "billing"), ("e2", "payment")), WEIGHTS)
    assert r["overall"] == approx(1.0, abs=1e-9)


def test_overall_is_weight_weighted_not_plain_mean():
    # billing (weight 3) f1=1.0; warranty (weight 1) f1=0.0.
    # SPEC 6.2: overall = (3*1 + 1*0) / (3+1) = 0.75. A plain mean gives 0.5.
    gold = {"e1": "billing", "e2": "billing", "e3": "warranty"}
    p = preds(("e1", "billing"), ("e2", "billing"), ("e3", "not a label"))
    r = score_model(gold, p, WEIGHTS)
    assert r["overall"] == approx(0.75, abs=1e-9)


def test_all_invalid_gives_overall_zero():
    # SPEC 4.1 + 5.1 + 6.2: only FNs everywhere -> every f1 = 0 -> overall 0.0.
    gold = {"e1": "billing", "e2": "shipping", "e3": "warranty"}
    r = score_model(gold, preds(("e1", "nonsense")), WEIGHTS)
    assert r["overall"] == approx(0.0, abs=1e-9)
    assert total_fp(r) == 0


# ---------------------------------------------------------------------------
# SPEC section 7: ROUND_HALF_UP to 4 decimal places.
# ---------------------------------------------------------------------------

def test_overall_rounding_is_half_up_not_bankers():
    # 59 warranty gold: 5 predicted "warranty" (TP), 54 predicted "billing"
    # (valid, wrong -> FN warranty, FP billing; billing has no gold so it is
    # excluded from the aggregate per 6.1).
    # f1(warranty) = 2*5 / (2*5 + 0 + 54) = 10/64 = 0.15625 exactly, and
    # overall = 0.15625 -> ROUND_HALF_UP -> 0.1563.
    # Banker's rounding (Python round()) yields 0.1562 and must fail here.
    gold = {f"w{i}": "warranty" for i in range(59)}
    p = [{"example_id": f"w{i}", "label": "warranty"} for i in range(5)]
    p += [{"example_id": f"w{i}", "label": "billing"} for i in range(5, 59)]
    r = score_model(gold, p, WEIGHTS)
    assert cat(r, "warranty")["f1"] == approx(0.15625, abs=1e-12)
    assert cat(r, "billing")["fp"] == 54  # SPEC 4.1: FP goes to predicted cat
    assert r["overall"] == approx(0.1563, abs=1e-9)


def test_overall_rounded_to_4dp():
    # SPEC 7.1: worked example 13/15 = 0.86666... must come back as exactly
    # the 4dp value, not the unrounded float.
    r = worked_example_result()
    assert r["overall"] == approx(0.8667, abs=1e-9)
    assert abs(r["overall"] - 13.0 / 15.0) > 1e-6  # i.e. it really was rounded


# ---------------------------------------------------------------------------
# SPEC section 8: ranking.
# ---------------------------------------------------------------------------

def test_rank_models_descending_by_score():
    scores = {"m-low": 0.1234, "m-high": 0.9876, "m-mid": 0.5555}
    assert rank_models(scores) == ["m-high", "m-mid", "m-low"]


def test_rank_models_ties_broken_by_name_ascending():
    scores = {"delta": 0.5, "alpha": 0.5, "echo": 0.7, "bravo": 0.5}
    assert rank_models(scores) == ["echo", "alpha", "bravo", "delta"]


def test_rank_models_tie_break_is_ascii_order():
    # SPEC 8.1: ascending lexicographic (ASCII) order; uppercase sorts first.
    scores = {"apple": 0.5, "Zebra": 0.5}
    assert rank_models(scores) == ["Zebra", "apple"]


def test_rank_models_returns_each_model_exactly_once():
    scores = {"a": 0.2, "b": 0.9, "c": 0.9, "d": 0.0, "e": 0.4}
    out = rank_models(scores)
    assert sorted(out) == ["a", "b", "c", "d", "e"]
    assert out == ["b", "c", "e", "a", "d"]
