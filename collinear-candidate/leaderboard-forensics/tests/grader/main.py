"""Verifier orchestrator: four criteria -> /logs/verifier/reward.json.

overall = 1.0 only if root_cause_fix == 1, data_repair == 1,
report_accuracy == 1, and the test-suite criterion PASSES (no false alarm
and kills >= KILLS_PASS; see check_mutation). Otherwise a weighted partial
(capped at 0.99) for diagnostics, in which the test-suite component is
BINARY: the instruction states a conjunctive contract ("fail every broken
one"), so a categorical miss contributes 0, not a fraction - averaging a
failed conjunctive contract into a near-1.0 partial would misreport the
outcome. The raw kill fraction stays in reward.json["test_suite"] and
grader_detail.json for diagnostics.
"""

import argparse
import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "reference"))
sys.path.insert(0, str(HERE.parent / "generator"))

import check_mutation  # noqa: E402
import check_repair  # noqa: E402
import check_report  # noqa: E402
import check_root_cause  # noqa: E402

# Test-suite pass/fail is decided by check_mutation (integer kills threshold);
# see check_mutation.KILLS_PASS.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    ws = Path(args.workspace)
    detail = {}

    def run(name, fn):
        try:
            score, info = fn(ws)
        except Exception:
            score, info = 0.0, {"error": traceback.format_exc()}
        detail[name] = {"score": score, **info}
        print(f"[grader] {name}: {score}", flush=True)
        return score

    rc = run("root_cause_fix", check_root_cause.check)
    dr = run("data_repair", check_repair.check)
    ra = run("report_accuracy", check_report.check)
    ts = run("test_suite", check_mutation.check)

    # Binary pass/fail for the conjunctive test-suite contract.
    suite_ok = bool(detail["test_suite"].get("suite_passed"))
    if rc == 1.0 and dr == 1.0 and ra == 1.0 and suite_ok:
        overall = 1.0
    else:
        ts_component = 1.0 if suite_ok else 0.0
        overall = min(0.99, round(
            0.25 * rc + 0.25 * dr + 0.2 * ra + 0.3 * ts_component, 4))

    reward = {
        "overall": overall,
        "root_cause_fix": rc,
        "data_repair": dr,
        "report_accuracy": ra,
        "test_suite": ts,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(reward, f, indent=2, sort_keys=True)
        f.write("\n")
    with open(out.parent / "grader_detail.json", "w", encoding="utf-8") as f:
        json.dump(detail, f, indent=2, sort_keys=True, default=str)
        f.write("\n")
    print(f"[grader] reward: {json.dumps(reward, sort_keys=True)}")


if __name__ == "__main__":
    main()
