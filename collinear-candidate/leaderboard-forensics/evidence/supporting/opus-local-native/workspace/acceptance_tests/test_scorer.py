"""Acceptance tests for the ticket-triage scorer against docs/SPEC.md.

The implementation under test is imported as:

    from scorer_under_test import score_model, rank_models

The grading harness places scorer_under_test.py next to these tests.
"""

import math

import pytest

from scorer_under_test import score_model, rank_models


CANONICAL_WEIGHTS = {
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


def approx(a, b, tol=1e-9):
    return math.isclose(a, b, rel_tol=0, abs_tol=tol)


# --- score_model -----------------------------------------------------------


def test_worked_example_from_spec_section_9():
    gold = {"e1": "billing", "e2": "billing", "e3": "refunds", "e4": "refunds"}
    preds = [
        {"example_id": "e1", "label": " Billing "},
        {"example_id": "e2", "label": "payment"},
        {"example_id": "e3", "label": "refund"},
        {"example_id": "e4", "label": "shipping issue"},
    ]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    assert out["overall"] == 0.8667
    pc = out["per_category"]
    assert (pc["billing"]["tp"], pc["billing"]["fp"], pc["billing"]["fn"]) == (2, 0, 0)
    assert (pc["refunds"]["tp"], pc["refunds"]["fp"], pc["refunds"]["fn"]) == (1, 0, 1)
    # SPEC 4.1: INVALID never produces an FP for any category.
    for c, d in pc.items():
        if c != "billing" and c != "refunds":
            assert d["fp"] == 0 and d["fn"] == 0 and d["tp"] == 0


def test_per_category_reports_every_weighted_category_even_when_unseen():
    gold = {"e1": "billing"}
    preds = [{"example_id": "e1", "label": "billing"}]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    # SPEC 6.1: per-category output includes every weighted category.
    assert set(out["per_category"].keys()) == set(CANONICAL_WEIGHTS.keys())
    assert out["per_category"]["warranty"] == {"tp": 0, "fp": 0, "fn": 0, "f1": 0.0}


def test_normalization_case_whitespace_and_separators():
    gold = {
        "a": "account_access",
        "b": "billing",
        "c": "data_privacy",
        "d": "feature_request",
    }
    preds = [
        {"example_id": "a", "label": "Sign-In"},          # §2.2 -> "sign in" -> account_access
        {"example_id": "b", "label": "  BILLING__ISSUE "},  # collapse + alias
        {"example_id": "c", "label": "GDPR request"},  # NBSP is whitespace (§2.1)
        {"example_id": "d", "label": "Feature   Request"},  # collapse internal ws
    ]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    for cat in ("account_access", "billing", "data_privacy", "feature_request"):
        assert out["per_category"][cat]["tp"] == 1
        assert out["per_category"][cat]["fp"] == 0
        assert out["per_category"][cat]["fn"] == 0


def test_invalid_prediction_counts_fn_only_no_fp():
    gold = {"e1": "billing"}
    preds = [{"example_id": "e1", "label": "not a real label"}]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    pc = out["per_category"]
    assert (pc["billing"]["tp"], pc["billing"]["fp"], pc["billing"]["fn"]) == (0, 0, 1)
    # No category should have gained an FP from the invalid prediction.
    assert sum(pc[c]["fp"] for c in pc) == 0


def test_missing_prediction_counts_fn_only():
    gold = {"e1": "billing", "e2": "billing"}
    preds = [{"example_id": "e1", "label": "billing"}]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    pc = out["per_category"]
    assert (pc["billing"]["tp"], pc["billing"]["fp"], pc["billing"]["fn"]) == (1, 0, 1)
    assert sum(pc[c]["fp"] for c in pc) == 0


def test_duplicate_first_occurrence_wins():
    # SPEC 3.3: first row in list order wins; later ones ignored.
    gold = {"e1": "billing"}
    preds = [
        {"example_id": "e1", "label": "billing"},
        {"example_id": "e1", "label": "refunds"},
    ]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    assert out["per_category"]["billing"]["tp"] == 1
    assert out["per_category"]["refunds"]["fp"] == 0

    # And the other way: first "wrong" wins, later "right" ignored.
    preds2 = [
        {"example_id": "e1", "label": "shipping"},
        {"example_id": "e1", "label": "billing"},
    ]
    out2 = score_model(gold, preds2, CANONICAL_WEIGHTS)
    assert out2["per_category"]["billing"]["tp"] == 0
    assert out2["per_category"]["billing"]["fn"] == 1
    assert out2["per_category"]["shipping"]["fp"] == 1


def test_stray_example_id_ignored_entirely():
    # SPEC 3.4: prediction row whose example_id is not in gold contributes nothing.
    gold = {"e1": "billing"}
    preds = [
        {"example_id": "e1", "label": "billing"},
        {"example_id": "ghost", "label": "shipping"},
    ]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    pc = out["per_category"]
    assert pc["shipping"] == {"tp": 0, "fp": 0, "fn": 0, "f1": 0.0}
    assert pc["billing"]["tp"] == 1


def test_wrong_but_valid_prediction_yields_fp_and_fn():
    gold = {"e1": "billing"}
    preds = [{"example_id": "e1", "label": "shipping"}]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    pc = out["per_category"]
    assert (pc["billing"]["tp"], pc["billing"]["fp"], pc["billing"]["fn"]) == (0, 0, 1)
    assert (pc["shipping"]["tp"], pc["shipping"]["fp"], pc["shipping"]["fn"]) == (0, 1, 0)


def test_overall_rounded_to_four_decimals():
    # SPEC 7.1: overall is rounded to 4 decimal places.
    # Six gold billing examples: 5 TP, 1 wrong (valid). F1 = 10/11 = 0.90909...
    # Only billing is gold-present, weight 3, overall = 0.90909... -> 0.9091.
    gold = {f"e{i}": "billing" for i in range(6)}
    preds = [{"example_id": f"e{i}", "label": "billing"} for i in range(5)]
    preds.append({"example_id": "e5", "label": "shipping"})
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    assert out["overall"] == 0.9091


def test_overall_only_aggregates_gold_present_categories():
    # SPEC 6.1: overall aggregate uses only categories with >= 1 gold example.
    gold = {"e1": "billing", "e2": "billing"}
    preds = [
        {"example_id": "e1", "label": "billing"},
        {"example_id": "e2", "label": "billing"},
    ]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    # All other categories have zero gold; overall should be 1.0 exactly.
    assert out["overall"] == 1.0


def test_per_category_f1_values_are_unrounded():
    # SPEC 7.1: per-category f1 values are NOT rounded.
    gold = {"e1": "refunds", "e2": "refunds", "e3": "refunds"}
    preds = [
        {"example_id": "e1", "label": "refunds"},
        {"example_id": "e2", "label": "refunds"},
        {"example_id": "e3", "label": "shipping"},
    ]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    # refunds: tp=2, fp=0, fn=1 -> F1 = 4/5 = 0.8 (finite decimal, still fine)
    assert approx(out["per_category"]["refunds"]["f1"], 4 / 5)
    # shipping: tp=0, fp=1, fn=0 -> F1 = 0 / 1 = 0.0
    assert out["per_category"]["shipping"]["f1"] == 0.0


def test_f1_zero_denominator_is_zero():
    # SPEC 5.1: denominator 0 -> F1 = 0.0. Category with no gold and no
    # predictions has tp=fp=fn=0 and must report f1=0.0.
    gold = {"e1": "billing"}
    preds = [{"example_id": "e1", "label": "billing"}]
    out = score_model(gold, preds, CANONICAL_WEIGHTS)
    for cat, d in out["per_category"].items():
        if d["tp"] == 0 and d["fp"] == 0 and d["fn"] == 0:
            assert d["f1"] == 0.0


def test_weights_universe_governs_reporting_but_not_validity():
    # SPEC 6.1: validity is judged against the canonical 12-label taxonomy,
    # regardless of `weights`. Here we pass a restricted weights map that
    # omits "shipping". A predicted "shipping" is still a valid canonical
    # label so it does NOT trigger the invalid-FN-only branch; it just is
    # not reported as its own row.
    gold = {"e1": "billing"}
    preds = [{"example_id": "e1", "label": "shipping"}]
    weights = {"billing": 3, "refunds": 2}
    out = score_model(gold, preds, weights)
    # billing must record an FN (mismatch).
    assert out["per_category"]["billing"]["fn"] == 1
    # per_category is limited to the passed weights.
    assert set(out["per_category"].keys()) == {"billing", "refunds"}


# --- rank_models -----------------------------------------------------------


def test_rank_models_descending_by_score():
    r = rank_models({"a": 0.8, "b": 0.9, "c": 0.7})
    assert r == ["b", "a", "c"]


def test_rank_models_ties_broken_by_name_ascending():
    # SPEC 8.1: ties -> ascending lexicographic (ASCII) by model name.
    r = rank_models({"zeta": 0.5, "alpha": 0.5, "mid": 0.9})
    assert r == ["mid", "alpha", "zeta"]


def test_rank_models_all_ties():
    r = rank_models({"b": 0.5, "a": 0.5, "c": 0.5})
    assert r == ["a", "b", "c"]
