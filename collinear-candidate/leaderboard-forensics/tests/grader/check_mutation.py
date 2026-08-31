"""Criterion 4: mutation-grade the agent's acceptance tests.

Round 0 runs the suite against THREE correct scorers: the reference plus two
behaviorally-identical, textually-rewritten variants (anti-grep hardening: a
suite that asserts on the implementation's source text instead of its
behavior false-alarms on a rewritten-but-correct variant). Any failure or
timeout against a correct implementation is a false alarm and caps the
criterion at 0.5.

Graded rounds run the suite against the GRADED mutant set: each graded mutant
violates exactly one SPEC clause AND has passed blind-reachability validation
(killed at least once by a solver with no knowledge of the mutants). Mutants
16 and 18 failed that validation (zero blind kills across every blind suite
evaluated against them) and are EXCLUDED from grading; they remain on disk as
documented, ungraded difficulty knobs. See tests/mutants/MUTANTS.md.

Diagnostic score = kills / 16; the criterion PASSES only when there is no
false alarm and kills >= KILLS_PASS (15 = n-1; the instruction says the suite
should fail EVERY broken implementation, so n-1 is leniency in the agent's
favor). The binary pass/fail is what the overall reward uses; the fraction is
kept for diagnostics.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS_DIR_NAME = "acceptance_tests"
MIN_TESTS = 8
ROUND_TIMEOUT = 45
# Graded set is explicit: mutants 01-15 plus 17. Mutants 16 and 18 are
# excluded by the blind-reachability rule (see module docstring) and must
# NOT be added back without a documented blind kill.
GRADED_MUTANTS = [f"mutant_{i:02d}" for i in range(1, 16)] + ["mutant_17"]
EXCLUDED_MUTANTS = ["mutant_16", "mutant_18"]
N_MUTANTS = len(GRADED_MUTANTS)  # 16
KILLS_PASS = 15


def _run_pytest(scratch, timeout=ROUND_TIMEOUT, extra=()):
    cmd = [sys.executable, "-m", "pytest", TESTS_DIR_NAME, "-x", "-q",
           "-p", "no:cacheprovider", *extra]
    env = {"PYTHONPATH": str(scratch), "PYTHONHASHSEED": "0",
           "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(scratch)}
    return subprocess.run(cmd, cwd=scratch, env=env, timeout=timeout,
                          capture_output=True, text=True)


def check(ws):
    ws = Path(ws)
    info = {"failures": [], "rounds": {}}
    fail = info["failures"].append

    suite = ws / TESTS_DIR_NAME
    if not suite.is_dir() or not list(suite.glob("test*.py")):
        return 0.0, {"failures": [f"{TESTS_DIR_NAME}/ missing or has no test*.py"]}
    blob = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(suite.glob("*.py")))
    if "scorer_under_test" not in blob:
        return 0.0, {"failures": ["suite never imports scorer_under_test"]}

    here = Path(__file__).resolve().parent.parent
    mutants = [here / "mutants" / f"{name}.py" for name in GRADED_MUTANTS]
    missing = [m.name for m in mutants if not m.is_file()]
    assert not missing, f"graded mutants missing on disk: {missing}"
    assert len(mutants) == N_MUTANTS
    correct_impls = [
        ("reference", here / "reference" / "ref_scorer.py"),
        ("reference_variant_a", here / "reference" / "ref_variant_a.py"),
        ("reference_variant_b", here / "reference" / "ref_variant_b.py"),
    ]

    def round_run(impl_path, collect_check=False):
        with tempfile.TemporaryDirectory() as td:
            scratch = Path(td)
            shutil.copytree(suite, scratch / TESTS_DIR_NAME)
            shutil.copy(impl_path, scratch / "scorer_under_test.py")
            if collect_check:
                try:
                    p = _run_pytest(scratch, extra=("--collect-only",))
                except subprocess.TimeoutExpired:
                    return "timeout", 0
                m = re.findall(r"(\d+) tests? collected", p.stdout + p.stderr)
                n = int(m[-1]) if m else 0
                if n < MIN_TESTS:
                    return "too_few", n
            try:
                p = _run_pytest(scratch)
            except subprocess.TimeoutExpired:
                return "timeout", None
            return ("pass" if p.returncode == 0 else "fail"), p.returncode

    # Round 0: every correct implementation must pass.
    false_alarm = False
    for i, (tag, path) in enumerate(correct_impls):
        status, n = round_run(path, collect_check=(i == 0))
        info["rounds"][tag] = status
        if status == "too_few":
            return 0.0, {"failures": [f"only {n} tests collected (min {MIN_TESTS})"]}
        if status == "timeout" and i == 0:
            return 0.0, {"failures": ["suite timed out against the correct scorer"]}
        if status != "pass":
            false_alarm = True
            fail(f"suite fails a CORRECT implementation ({tag}) - false alarm")

    kills = 0
    for mp in mutants:
        status, _ = round_run(mp)
        killed = status == "fail" or (status == "timeout" and not false_alarm)
        info["rounds"][mp.stem] = f"{status} ({'killed' if killed else 'survived'})"
        if killed:
            kills += 1

    score = kills / N_MUTANTS
    if false_alarm:
        score = min(score, 0.5)
    info["kills"] = kills
    info["n_mutants"] = N_MUTANTS
    info["kills_required"] = KILLS_PASS
    info["suite_passed"] = (not false_alarm) and kills >= KILLS_PASS
    return round(score, 4), info
