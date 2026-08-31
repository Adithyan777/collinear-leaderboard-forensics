"""Oracle repair: measure the corruption, rebuild the artifacts with the
fixed pipeline, and write report.json. Runs inside the task container with
cwd = /app/workspace."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

WS = Path("/app/workspace")


N_MODELS = 6
SHARD_SIZE = 333
CORRECT_PER_SHARD = N_MODELS * SHARD_SIZE


def shard_anomalies():
    """Per-shard row deltas in the August results table vs a correct scoring."""
    conn = sqlite3.connect(WS / "db" / "results.sqlite")
    try:
        per_shard = dict(conn.execute(
            "SELECT shard, COUNT(*) FROM results GROUP BY shard"))
    finally:
        conn.close()
    anomalies = []
    for i in range(12):
        shard = f"shard_{i:02d}"
        n = per_shard.get(shard, 0)
        if n > CORRECT_PER_SHARD:
            anomalies.append({"shard": shard, "defect": "surplus_rows",
                              "n_rows": n - CORRECT_PER_SHARD})
        elif n < CORRECT_PER_SHARD:
            anomalies.append({"shard": shard, "defect": "missing_rows",
                              "n_rows": CORRECT_PER_SHARD - n})
    return anomalies


def main():
    anomalies = shard_anomalies()

    # rebuild from raw data with the fixed pipeline (fresh full run)
    (WS / "db" / "results.sqlite").unlink(missing_ok=True)
    (WS / "state" / "checkpoint.json").unlink(missing_ok=True)
    for args in (["-m", "pipeline.run_scoring"],
                 ["-m", "pipeline.build_leaderboard"],
                 ["-m", "pipeline.report_md"]):
        subprocess.run([sys.executable, *args], cwd=WS, check=True)

    # corrected numbers from the rebuilt leaderboard
    import csv
    overall, ranking = {}, []
    with open(WS / "leaderboard.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ranking.append(row["model"])
            overall[row["model"]] = float(row["overall"])

    report = {
        "root_cause": {"file": "pipeline/checkpoint.py",
                        "function": "resume_plan"},
        "shard_anomalies": anomalies,
        "corrected_overall": overall,
        "corrected_ranking": ranking,
    }
    with open(WS / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
    print("oracle repair complete")


if __name__ == "__main__":
    main()
