# Ticket-Triage Benchmark -- Scoring Specification

| Field   | Value                |
|---------|----------------------|
| Version | v2.3                 |
| Owner   | eval-platform team   |
| Status  | Authoritative        |

This document defines how predictions from the ticket-triage benchmark are normalized, scored, and ranked. It covers every step from raw prediction files through the final leaderboard order.

This document is authoritative. Where `pipeline/scorer.py` and this document disagree, this document wins. Acceptance tests for the scorer should treat this document as the contract.

---

## 1. Inputs

**Gold labels.** File `data/gold/gold_labels.jsonl`, one JSON object per line:

```json
{"example_id": "string", "label": "string"}
```

Gold labels are always canonical taxonomy labels (never aliases, never pre-normalized).

**Predictions.** Files `data/predictions/shard_00.jsonl` through `data/predictions/shard_11.jsonl`, one JSON object per line:

```json
{"example_id": "string", "model": "string", "label": "string"}
```

**Category weights.** Defined in `pipeline/config.py` (`CATEGORY_WEIGHTS`) and reproduced here as the canonical taxonomy table:

| Category         | Weight |
|------------------|--------|
| account_access   | 3      |
| billing          | 3      |
| technical_error  | 3      |
| product_defect   | 3      |
| refunds          | 2      |
| shipping         | 2      |
| returns          | 2      |
| data_privacy     | 2      |
| subscription     | 2      |
| warranty         | 1      |
| feature_request  | 1      |
| general_inquiry  | 1      |

---

## 2. Prediction normalization

Normalization applies to **predicted labels only**. Gold labels are used as-is.

**§2.1** Lowercase the label, strip leading and trailing whitespace, and collapse every internal run of whitespace to a single space. Whitespace means Unicode whitespace as recognized by Python's `str.split()` (so U+00A0 counts).

**§2.2** Replace every underscore (`_`) and hyphen (`-`) with a space. This happens before whitespace collapsing, so `"Sign-In"` becomes `"sign in"` and `"billing__issue"` becomes `"billing issue"`.

**§2.3** Alias mapping. After §2.1--§2.2, if the resulting string appears in the alias table below, replace it with the mapped canonical label. The match is exact, whole-string only. The mapping is applied at most once: the alias output is final and is never re-applied. Canonical labels that do not appear in the table pass through unchanged.

### Alias table

39 entries. Normalized form on the left, canonical label on the right.
(The space-separated forms of taxonomy labels are listed as aliases so a
canonical label still maps to itself after separator normalization.)

| Normalized form    | Canonical label  |
|--------------------|------------------|
| login issue        | account_access   |
| sign in            | account_access   |
| signin             | account_access   |
| locked out         | account_access   |
| payment            | billing          |
| billing issue      | billing          |
| invoice            | billing          |
| overcharge         | billing          |
| refund             | refunds          |
| money back         | refunds          |
| bug                | technical_error  |
| crash              | technical_error  |
| error              | technical_error  |
| site down          | technical_error  |
| defect             | product_defect   |
| broken item        | product_defect   |
| faulty             | product_defect   |
| delivery           | shipping         |
| package            | shipping         |
| tracking           | shipping         |
| return             | returns          |
| exchange           | returns          |
| privacy            | data_privacy     |
| gdpr request       | data_privacy     |
| delete my data     | data_privacy     |
| cancel subscription| subscription     |
| upgrade plan       | subscription     |
| downgrade          | subscription     |
| guarantee          | warranty         |
| suggestion         | feature_request  |
| feature idea       | feature_request  |
| question           | general_inquiry  |
| other              | general_inquiry  |
| account access     | account_access   |
| technical error    | technical_error  |
| product defect     | product_defect   |
| data privacy       | data_privacy     |
| feature request    | feature_request  |
| general inquiry    | general_inquiry  |

---

## 3. Validity and row handling

**§3.1** After normalization (§2), if the label is not one of the 12 canonical taxonomy labels, the prediction is INVALID.

**§3.2** If a gold example has no prediction row for a given model, that model's prediction for it is INVALID.

**§3.3** If the same `example_id` appears more than once for one model, the **first** occurrence wins and later ones are ignored. Order is defined as: shard filename ascending (`shard_00` ... `shard_11`), then row order within the file. At the API level: the order of the `predictions` list as passed.

**§3.4** A prediction row whose `example_id` does not exist in the gold set is ignored entirely. It contributes nothing: no false positive, no effect at all.

---

## 4. Counting

**§4.1** For each gold example, exactly one of the following applies:

- The final (normalized, aliased) predicted label **equals** the gold label: count one **TP** for that category.
- The prediction is valid but **differs** from the gold label: count one **FP** for the predicted category AND one **FN** for the gold category.
- The prediction is **INVALID** (§3.1 or §3.2): count one **FN** for the gold category only. INVALID predictions never produce an FP for any category.

---

## 5. Per-category F1

**§5.1**

```
F1_c = 2 * TP_c / (2 * TP_c + FP_c + FN_c)
```

If the denominator is 0, `F1_c = 0.0`.

---

## 6. Aggregation

**§6.1** The per-category output includes **every** category in the weights table, even those with zero gold examples (report `tp=0, fp=0, fn=0, f1=0.0` for unseen categories). The overall aggregate, however, includes **only** categories with at least one gold example. The `weights` mapping passed to the scorer defines the reporting and aggregation universe; validity (§3.1) is always judged against the canonical 12-label taxonomy, regardless of `weights`.

**§6.2** The overall score before rounding:

```
overall_unrounded = sum(w_c * F1_c) / sum(w_c)
```

Both sums run over gold-present categories only. All intermediate values stay unrounded.

---

## 7. Rounding

**§7.1** The final overall score is rounded to 4 decimal places using `ROUND_HALF_UP`.

Example: `0.86665` rounds to `0.8667`.

> **Warning.** Python's built-in `round()` uses banker's rounding and will produce `0.8666` for the value above. Do not use it. Use:
>
> ```python
> from decimal import Decimal, ROUND_HALF_UP
> Decimal(str(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
> ```

Per-category `f1` values in the output are **not** rounded.

---

## 8. Ranking

**§8.1** Models are ranked by rounded overall score, descending. Ties are broken by model name, ascending lexicographic (ASCII) order.

---

## 9. Worked end-to-end example

### Setup

Only two categories carry gold examples: billing (weight 3) and refunds (weight 2).

Gold set:

| example_id | label   |
|------------|---------|
| e1         | billing |
| e2         | billing |
| e3         | refunds |
| e4         | refunds |

### Model predictions and normalization

| example_id | raw label        | after §2.1--2.2    | after §2.3 (alias) | result         |
|------------|------------------|---------------------|---------------------|----------------|
| e1         | `" Billing "`    | `"billing"`         | (canonical, no alias) | TP(billing)  |
| e2         | `"payment"`      | `"payment"`         | `"billing"`         | TP(billing)    |
| e3         | `"refund"`       | `"refund"`          | `"refunds"`         | TP(refunds)    |
| e4         | `"shipping issue"`| `"shipping issue"` | not a taxonomy label, not an alias | INVALID, FN(refunds), no FP |

### Counts and per-category F1

| Category | TP | FP | FN | F1                          |
|----------|----|----|----|------------------------------|
| billing  | 2  | 0  | 0  | 4/4 = 1.0                   |
| refunds  | 1  | 0  | 1  | 2/(2+0+1) = 2/3 = 0.6666... |

### Overall score

```
overall = (3 * 1.0 + 2 * (2/3)) / (3 + 2)
        = (3 + 4/3) / 5
        = 13/15
        = 0.8666666...
```

Rounded with `ROUND_HALF_UP` to 4 decimal places: **0.8667**.

### Micro-examples

**(a) Duplicate handling (§3.3).** If `e1` appears twice for a model, first with label `"billing"` then with label `"refunds"`, the `"billing"` row is used.

**(b) Separator chain (§2.1--2.2, §2.3).** `"Sign-In"` normalizes to `"sign in"` (§2.1--2.2), then maps via alias to `account_access` (§2.3).

---

## 10. Scorer API

Both functions live in `pipeline/scorer.py` and must be importable with these exact names and signatures.

```python
def score_model(gold: dict[str, str], predictions: list[dict], weights: dict[str, float]) -> dict:
    """Score a single model's predictions against the gold set.

    Args:
        gold: example_id -> canonical label.
        predictions: [{"example_id": str, "label": str}, ...] in canonical order (see §3.3).
        weights: category -> weight.

    Returns:
        {"per_category": {cat: {"tp": int, "fp": int, "fn": int, "f1": float}},
         "overall": float}

    overall is rounded per §7.1. Per-category f1 values are unrounded.
    """


def rank_models(overall_scores: dict[str, float]) -> list[str]:
    """Rank models for the leaderboard.

    Args:
        overall_scores: model name -> rounded overall score.

    Returns:
        Model names ranked per §8.1 (descending score, ascending name on ties).
    """
```
