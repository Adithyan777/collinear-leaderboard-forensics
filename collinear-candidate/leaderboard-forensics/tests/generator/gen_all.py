"""Build the complete committed workspace from AGENT_SEED, with assertions.

Usage: python tests/generator/gen_all.py [--workspace PATH]
Idempotent and deterministic: same seed -> byte-identical workspace.
"""

import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "reference"))

import dress  # noqa: E402
import genworld  # noqa: E402
import ref_scorer  # noqa: E402
from seeds import AGENT_SEED, JULY_SEED  # noqa: E402

TASK_DIR = HERE.parent.parent


def canonical_predictions(world, model):
    rows = []
    for shard in genworld.SHARDS:
        with open(world / "data" / "predictions" / f"{shard}.jsonl", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row["model"] == model:
                    rows.append(row)
    return rows


def ref_scores(world):
    gold = {}
    with open(world / "data" / "gold" / "gold_labels.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            gold[r["example_id"]] = r["label"]
    scores = {}
    for model in sorted(genworld.MODELS_AUG):
        preds = canonical_predictions(world, model)
        scores[model] = ref_scorer.score_model(
            gold, preds, ref_scorer.TAXONOMY_WEIGHTS)["overall"]
    return scores


def parse_leaderboard(path):
    rank, overall = {}, {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rank[row["model"]] = int(row["rank"])
            overall[row["model"]] = float(row["overall"])
    return {"rank": rank, "overall": overall}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace",
                    default=str(TASK_DIR / "environment" / "workspace"))
    args = ap.parse_args()
    ws = Path(args.workspace).resolve()

    for sub in ["data/gold", "data/predictions", "db", "state", "logs",
                "tickets", "docs/archive"]:
        (ws / sub).mkdir(parents=True, exist_ok=True)
    for stale in ["db/results.sqlite", "state/checkpoint.json"]:
        (ws / stale).unlink(missing_ok=True)

    crash_idx = genworld.crash_index(AGENT_SEED)
    hot_shard = genworld.SHARDS[crash_idx - 1]
    print(f"crash shard index {crash_idx} ({genworld.SHARDS[crash_idx]}); "
          f"hot shard {hot_shard}")

    # 1. clean world (hot shard gets doubled by the bug; cold shard gets skipped)
    genworld.build_clean_world(ws, AGENT_SEED, genworld.MODELS_AUG,
                               hot_shard=hot_shard,
                               cold_shard=genworld.SHARDS[crash_idx])

    # innocent-change neutrality: no NBSP anywhere in the data
    for p in sorted((ws / "data").rglob("*.jsonl")):
        assert " " not in p.read_text(encoding="utf-8"), p

    # 2. crash + buggy resume via the real pipeline
    import random as _random

    import corrupt
    crash_lines, resume_lines, crash_shard = corrupt.run_crash_and_buggy_resume(
        ws, crash_idx, ws / "logs")
    log_rng = _random.Random(AGENT_SEED * 17 + 3)
    dress.write_crash_log(ws, crash_lines, crash_shard,
                          ws / "logs" / "score_run_20260812_091403.log", log_rng)
    dress.write_resume_log(ws, resume_lines,
                           ws / "logs" / "score_run_20260812_094117.log", log_rng)

    # 3. July archive (previous month, correct run, raw data not retained)
    with tempfile.TemporaryDirectory() as td:
        jul = Path(td)
        genworld.build_clean_world(jul, JULY_SEED, genworld.MODELS_JUL)
        jgold_scores = {}
        gold = {}
        with open(jul / "data" / "gold" / "gold_labels.jsonl", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                gold[r["example_id"]] = r["label"]
        for model in sorted(genworld.MODELS_JUL):
            preds = canonical_predictions(jul, model)
            jgold_scores[model] = ref_scorer.score_model(
                gold, preds, ref_scorer.TAXONOMY_WEIGHTS)["overall"]
        jranking = ref_scorer.rank_models(jgold_scores)
        dress.write_july_archive(ws / "docs" / "archive" / "RESULTS_2026-07.md",
                                 jgold_scores, jranking,
                                 len(genworld.MODELS_JUL) * genworld.N_EXAMPLES)
        july = {"rank": {m: i for i, m in enumerate(jranking, 1)},
                "overall": jgold_scores}

    # 4. dressing
    corrupted = parse_leaderboard(ws / "leaderboard.csv")
    dress.write_ticket(ws, corrupted, july, ws / "tickets" / "TICKET-4127.md")
    dress.write_readme(ws)
    dress.write_runbook(ws)
    dress.write_changelog(ws)

    # 5. reference (corrected) truth + expected report
    corrected = ref_scores(ws)
    corrected_ranking = ref_scorer.rank_models(corrected)

    conn = sqlite3.connect(ws / "db" / "results.sqlite")
    dupes = conn.execute(
        "SELECT COUNT(*) FROM (SELECT model, example_id FROM results "
        "GROUP BY model, example_id HAVING COUNT(*) > 1)").fetchone()[0]
    dupe_shards = sorted({r[0] for r in conn.execute(
        "SELECT DISTINCT shard FROM results GROUP BY model, example_id, shard "
        "HAVING COUNT(*) > 1")})
    scored_shards = {r[0] for r in conn.execute("SELECT DISTINCT shard FROM results")}
    per_model_rows = {r[0]: r[1] for r in conn.execute(
        "SELECT model, COUNT(*) FROM results GROUP BY model")}
    conn.close()

    skipped = sorted(set(genworld.SHARDS) - scored_shards)

    # neutral forensic anomaly list: per-shard row deltas vs a correct scoring
    correct_per_shard = genworld.SHARD_SIZE * len(genworld.MODELS_AUG)
    conn = sqlite3.connect(ws / "db" / "results.sqlite")
    per_shard = dict(conn.execute(
        "SELECT shard, COUNT(*) FROM results GROUP BY shard"))
    conn.close()
    anomalies = []
    for shard in genworld.SHARDS:
        n = per_shard.get(shard, 0)
        if n > correct_per_shard:
            anomalies.append({"shard": shard, "defect": "surplus_rows",
                              "n_rows": n - correct_per_shard})
        elif n < correct_per_shard:
            anomalies.append({"shard": shard, "defect": "missing_rows",
                              "n_rows": correct_per_shard - n})

    expected = {
        "root_cause": {"file": "pipeline/checkpoint.py", "function": "resume_plan"},
        "shard_anomalies": anomalies,
        "corrected_overall": corrected,
        "corrected_ranking": corrected_ranking,
    }
    assert anomalies == [
        {"shard": dupe_shards[0], "defect": "surplus_rows", "n_rows": dupes},
        {"shard": skipped[0], "defect": "missing_rows",
         "n_rows": correct_per_shard},
    ], anomalies

    # 6. assertions
    corrupted_ranking = [m for m, _ in
                         sorted(corrupted["rank"].items(), key=lambda kv: kv[1])]
    assert len(dupe_shards) == 1 and len(skipped) == 1, (dupe_shards, skipped)
    assert dupe_shards[0] == genworld.SHARDS[crash_idx - 1]
    assert skipped[0] == crash_shard
    assert dupes == len(genworld.MODELS_AUG) * genworld.SHARD_SIZE, dupes
    assert corrupted_ranking != corrected_ranking, "corruption must change ranking"
    b_corrupted = corrupted["rank"]["bramble-x"]
    b_corrected = corrected_ranking.index("bramble-x") + 1
    assert b_corrupted < b_corrected, (
        f"bramble must jump under corruption: {b_corrupted} vs {b_corrected}")
    assert july["rank"]["bramble-x"] == 4, july["rank"]
    vals = sorted(corrected.values())
    assert all(abs(a - b) > 0.0005 for a, b in zip(vals, vals[1:])), \
        "corrected scores too close / tied"
    assert set(per_model_rows.values()) == {genworld.N_EXAMPLES}, \
        per_model_rows  # double-count exactly masks the skip
    md = (ws / "RESULTS.md").read_text(encoding="utf-8")
    for m, s in corrupted["overall"].items():
        assert f"{s:.4f}" in md, (m, s)

    # 7. expected files + checksums
    exp_dir = TASK_DIR / "tests" / "expected"
    exp_dir.mkdir(parents=True, exist_ok=True)
    with open(exp_dir / "report_expected.json", "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=2, sort_keys=True)
        f.write("\n")
    with open(exp_dir / "leaderboard_ref.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "model", "overall"])
        for i, m in enumerate(corrected_ranking, 1):
            w.writerow([i, m, f"{corrected[m]:.4f}"])

    for pyc in ws.rglob("__pycache__"):
        shutil.rmtree(pyc)
    checks = []
    for p in sorted(ws.rglob("*")):
        if p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            checks.append(f"{h}  {p.relative_to(ws)}")
    (exp_dir / "world_checksums.txt").write_text("\n".join(checks) + "\n",
                                                 encoding="utf-8")

    print(f"corrupted ranking: {corrupted_ranking}")
    print(f"corrected ranking: {corrected_ranking}")
    print(f"expected anomalies: {expected['shard_anomalies']}")
    print("gen_all: OK")


if __name__ == "__main__":
    main()
