"""Criterion 3: report.json matches reference facts. Score = fraction of the
7 checked fields that are correct."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gradelib  # noqa: E402

ACCEPTED_FILES = {"pipeline/checkpoint.py", "checkpoint.py",
                  "/app/workspace/pipeline/checkpoint.py"}
ACCEPTED_FUNCS = {"resume_plan", "checkpoint.resume_plan",
                  "pipeline.checkpoint.resume_plan"}


def check(ws):
    ws = Path(ws)
    info = {"failures": [], "fields": {}}
    fail = info["failures"].append

    path = ws / "report.json"
    if not path.exists():
        return 0.0, {"failures": ["report.json missing"]}
    try:
        rep = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return 0.0, {"failures": [f"report.json invalid JSON: {e}"]}

    expected = json.loads(
        (Path(__file__).resolve().parent.parent / "expected" /
         "report_expected.json").read_text(encoding="utf-8"))
    # live cross-check: expected corrected values must match an in-container
    # recomputation (guards against a stale expected file)
    ref_overall, ref_ranking = gradelib.reference_truth(ws)
    for m, v in expected["corrected_overall"].items():
        assert abs(ref_overall[m] - v) <= gradelib.TOL, (m, v, ref_overall[m])
    assert expected["corrected_ranking"] == ref_ranking

    def grade(name, ok):
        info["fields"][name] = bool(ok)
        if not ok:
            fail(name)

    rc = rep.get("root_cause") or {}
    f_ok = str(rc.get("file", "")).lstrip("./") in ACCEPTED_FILES
    fn_ok = str(rc.get("function", "")) in ACCEPTED_FUNCS
    grade("root_cause", f_ok and fn_ok)

    def anomaly_key(entries):
        try:
            return sorted((e["shard"], e["defect"], int(e["n_rows"]))
                          for e in entries)
        except (KeyError, TypeError, ValueError):
            return None
    grade("shard_anomalies",
          anomaly_key(rep.get("shard_anomalies") or []) ==
          anomaly_key(expected["shard_anomalies"]))
    co = rep.get("corrected_overall") or {}
    co_ok = (set(co) == set(expected["corrected_overall"]) and all(
        isinstance(co[m], (int, float)) and
        abs(co[m] - expected["corrected_overall"][m]) <= gradelib.TOL
        for m in expected["corrected_overall"]))
    grade("corrected_overall", co_ok)
    grade("corrected_ranking",
          rep.get("corrected_ranking") == expected["corrected_ranking"])

    n_ok = sum(1 for v in info["fields"].values() if v)
    return round(n_ok / len(info["fields"]), 4), info
