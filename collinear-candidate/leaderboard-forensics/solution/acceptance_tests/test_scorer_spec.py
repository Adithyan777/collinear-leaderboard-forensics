"""Acceptance tests for the ticket-triage scorer, per docs/SPEC.md.
Each test pins one clause of the SPEC to its worked semantics."""

from scorer_under_test import score_model, rank_models

W_BR = {"billing": 3, "refunds": 2}


def test_worked_example_section9():
    gold = {"e1": "billing", "e2": "billing", "e3": "refunds", "e4": "refunds"}
    preds = [
        {"example_id": "e1", "label": " Billing "},
        {"example_id": "e2", "label": "payment"},
        {"example_id": "e3", "label": "refund"},
        {"example_id": "e4", "label": "shipping issue"},
    ]
    r = score_model(gold, preds, W_BR)
    assert r["per_category"]["billing"] == {"tp": 2, "fp": 0, "fn": 0, "f1": 1.0}
    b = r["per_category"]["refunds"]
    assert (b["tp"], b["fp"], b["fn"]) == (1, 0, 1)
    assert abs(b["f1"] - 2 / 3) < 1e-9
    assert r["overall"] == 0.8667


def test_lowercase_and_whitespace_2_1():
    r = score_model({"e1": "billing"},
                    [{"example_id": "e1", "label": "  BILLING  "}], W_BR)
    assert r["per_category"]["billing"]["tp"] == 1


def test_separators_2_2():
    r = score_model({"e1": "billing"},
                    [{"example_id": "e1", "label": "billing_issue"}], W_BR)
    assert r["per_category"]["billing"]["tp"] == 1  # -> "billing issue" -> alias
    r2 = score_model({"e1": "account_access"},
                     [{"example_id": "e1", "label": "Sign-In"}], W_BR | {"account_access": 3})
    assert r2["per_category"]["account_access"]["tp"] == 1


def test_alias_mapping_2_3():
    r = score_model({"e1": "billing", "e2": "refunds"},
                    [{"example_id": "e1", "label": "payment"},
                     {"example_id": "e2", "label": "money back"}], W_BR)
    assert r["per_category"]["billing"]["tp"] == 1
    assert r["per_category"]["refunds"]["tp"] == 1


def test_invalid_is_fn_only_never_fp_3_1():
    w = {"billing": 3, "general_inquiry": 1}
    gold = {"e1": "billing", "e2": "general_inquiry"}
    preds = [{"example_id": "e1", "label": "utter junk zzz"},
             {"example_id": "e2", "label": "general_inquiry"}]
    r = score_model(gold, preds, w)
    assert r["per_category"]["billing"] == {"tp": 0, "fp": 0, "fn": 1, "f1": 0.0}
    assert r["per_category"]["general_inquiry"]["fp"] == 0
    assert r["per_category"]["general_inquiry"]["f1"] == 1.0


def test_missing_prediction_is_invalid_fn_3_2():
    gold = {"e1": "billing", "e2": "billing"}
    r = score_model(gold, [{"example_id": "e1", "label": "billing"}], W_BR)
    c = r["per_category"]["billing"]
    assert (c["tp"], c["fn"]) == (1, 1)
    assert abs(c["f1"] - 2 / 3) < 1e-9


def test_duplicate_first_occurrence_wins_3_3():
    gold = {"e1": "billing"}
    r = score_model(gold, [{"example_id": "e1", "label": "billing"},
                           {"example_id": "e1", "label": "refunds"}], W_BR)
    assert r["per_category"]["billing"]["tp"] == 1
    assert r["per_category"]["refunds"]["fp"] == 0


def test_unknown_example_id_ignored_3_4():
    gold = {"e1": "billing"}
    r = score_model(gold, [{"example_id": "e1", "label": "billing"},
                           {"example_id": "zzz-1", "label": "refunds"},
                           {"example_id": "zzz-2", "label": "billing"}], W_BR)
    assert r["per_category"]["refunds"]["fp"] == 0
    assert r["per_category"]["billing"] == {"tp": 1, "fp": 0, "fn": 0, "f1": 1.0}
    assert r["overall"] == 1.0


def test_f1_formula_5_1():
    # billing: tp=1; refunds predicted where gold=billing: fp for refunds
    gold = {"e1": "billing", "e2": "billing", "e3": "refunds"}
    preds = [{"example_id": "e1", "label": "billing"},
             {"example_id": "e2", "label": "refunds"},
             {"example_id": "e3", "label": "refunds"}]
    r = score_model(gold, preds, W_BR)
    b = r["per_category"]["billing"]   # tp1 fn1 -> 2/3
    f = r["per_category"]["refunds"]   # tp1 fp1 -> 2/3
    assert abs(b["f1"] - 2 / 3) < 1e-9
    assert abs(f["f1"] - 2 / 3) < 1e-9


def test_aggregation_gold_present_only_6_1():
    w = {"billing": 3, "refunds": 2, "warranty": 1, "shipping": 2}
    r = score_model({"e1": "billing"},
                    [{"example_id": "e1", "label": "billing"}], w)
    # only billing has gold examples; others excluded from the aggregate
    assert r["overall"] == 1.0
    for cat in ("refunds", "warranty", "shipping"):
        assert r["per_category"][cat] == {"tp": 0, "fp": 0, "fn": 0, "f1": 0.0}


def test_rounding_half_up_7_1():
    # billing f1 = 2/32 = 0.0625 (1 correct, 30 missing); refunds f1 = 1.0
    # overall with weights 1,1 = 0.53125 -> must round UP to 0.5313
    gold = {f"a{i:02d}": "billing" for i in range(31)}
    gold["b0"] = "refunds"
    preds = [{"example_id": "a00", "label": "billing"},
             {"example_id": "b0", "label": "refunds"}]
    r = score_model(gold, preds, {"billing": 1, "refunds": 1})
    assert r["overall"] == 0.5313


def test_zero_denominator_f1_is_zero_5_1():
    r = score_model({"e1": "billing"},
                    [{"example_id": "e1", "label": "junk###"}], W_BR)
    assert r["per_category"]["refunds"]["f1"] == 0.0


def test_ranking_desc_ties_by_name_8_1():
    assert rank_models({"beta": 0.5, "alpha": 0.5, "gamma": 0.7}) == \
        ["gamma", "alpha", "beta"]
    assert rank_models({"m2": 0.61, "m1": 0.6052}) == ["m2", "m1"]


def test_invalid_no_fp_for_any_category_4_1():
    # full-taxonomy weights; the gold category itself must not gain an FP
    w = {"account_access": 3, "billing": 3, "technical_error": 3,
         "product_defect": 3, "refunds": 2, "shipping": 2, "returns": 2,
         "data_privacy": 2, "subscription": 2, "warranty": 1,
         "feature_request": 1, "general_inquiry": 1}
    gold = {"e1": "billing", "e2": "billing"}
    preds = [{"example_id": "e1", "label": "complete nonsense ###"},
             {"example_id": "e2", "label": "billing"}]
    r = score_model(gold, preds, w)
    for cat, c in r["per_category"].items():
        assert c["fp"] == 0, f"INVALID produced an FP for {cat}"
    b = r["per_category"]["billing"]
    assert (b["tp"], b["fn"]) == (1, 1)
    assert abs(b["f1"] - 2 / 3) < 1e-9  # not 0.5: fp must stay 0


def test_duplicate_invalid_then_valid_first_still_wins_3_3():
    gold = {"e1": "billing"}
    preds = [{"example_id": "e1", "label": "garbage@@"},
             {"example_id": "e1", "label": "billing"}]
    r = score_model(gold, preds, W_BR)
    c = r["per_category"]["billing"]
    assert (c["tp"], c["fp"], c["fn"]) == (0, 0, 1)  # first occurrence, INVALID


def test_unicode_whitespace_2_1():
    w = {"account_access": 3}
    for raw in ("sign in", "sign\tin", "sign   in"):
        r = score_model({"e1": "account_access"},
                        [{"example_id": "e1", "label": raw}], w)
        assert r["per_category"]["account_access"]["tp"] == 1, repr(raw)


def test_per_category_f1_unrounded_7_1():
    # tp=1, fn=1 -> f1 = 2/3, which must be reported unrounded (not 0.6667)
    r = score_model({"e1": "refunds", "e2": "refunds"},
                    [{"example_id": "e1", "label": "refunds"}], {"refunds": 1})
    f1 = r["per_category"]["refunds"]["f1"]
    assert abs(f1 - 2 / 3) < 1e-12, f1


def test_alias_exact_whole_string_only_2_3():
    for raw in ("payment issue", "invoices", "refund request"):
        r = score_model({"e1": "billing"},
                        [{"example_id": "e1", "label": raw}], W_BR)
        c = r["per_category"]["billing"]
        assert (c["tp"], c["fn"]) == (0, 1), repr(raw)  # INVALID, no alias rescue
        assert r["per_category"]["refunds"]["fp"] == 0, repr(raw)


def test_rounding_is_half_up_not_ceiling_7_1():
    # overall = 1/3 = 0.33333... must round DOWN to 0.3333 (its 5th decimal
    # is 3, below the half). A ceiling implementation reports 0.3334, and
    # the SPEC 9 example (0.86665 -> 0.8667) cannot distinguish it.
    gold = {f"b{i}": "billing" for i in range(5)}
    preds = [{"example_id": "b0", "label": "billing"}] + \
        [{"example_id": f"b{i}", "label": "junk##"} for i in range(1, 5)]
    r = score_model(gold, preds, {"billing": 1})
    # billing: tp=1, fn=4 -> f1 = 2/6 = 1/3; only gold-present category.
    assert abs(r["overall"] - 0.3333) < 5e-9, r["overall"]


def test_intermediates_stay_unrounded_in_aggregation_6_2():
    # billing f1 = 2/3, refunds f1 = 0.5, equal weights.
    # True overall = 7/12 = 0.583333... -> 0.5833.
    # Rounding the intermediate f1 first gives (0.6667 + 0.5)/2 = 0.58335
    # -> 0.5834, so this input detects pre-aggregation rounding.
    gold = {"b1": "billing", "b2": "billing",
            "r1": "refunds", "r2": "refunds", "r3": "refunds"}
    preds = [{"example_id": "b1", "label": "billing"},
             {"example_id": "b2", "label": "junk##"},
             {"example_id": "r1", "label": "refunds"},
             {"example_id": "r2", "label": "junk##"},
             {"example_id": "r3", "label": "junk##"}]
    r = score_model(gold, preds, {"billing": 1, "refunds": 1})
    assert abs(r["overall"] - 0.5833) < 5e-9, r["overall"]
    # and the reported f1 itself stays unrounded (7.1)
    assert abs(r["per_category"]["billing"]["f1"] - 2 / 3) < 1e-12


def test_validity_universe_is_canonical_taxonomy_6_1():
    # 6.1: weights defines the reporting/aggregation universe only; validity
    # is judged against the canonical 12-label taxonomy REGARDLESS of
    # weights. "widget" is in the weights universe here but is not a
    # canonical label, so predicting it is INVALID: FN for gold, no FP
    # anywhere - not even for the reported "widget" bucket.
    r = score_model({"e1": "billing"},
                    [{"example_id": "e1", "label": "widget"}],
                    {"billing": 1, "widget": 1})
    w = r["per_category"]["widget"]
    assert (w["tp"], w["fp"], w["fn"], w["f1"]) == (0, 0, 0, 0.0)
    b = r["per_category"]["billing"]
    assert (b["tp"], b["fp"], b["fn"]) == (0, 0, 1)
    assert r["overall"] == 0.0
