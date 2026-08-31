#!/bin/bash
set -euo pipefail

# 1. root-cause fix: correct resume logic + idempotent shard writes
cp /solution/fixed/checkpoint.py /app/workspace/pipeline/checkpoint.py
cp /solution/fixed/run_scoring.py /app/workspace/pipeline/run_scoring.py

# 2+3. repair artifacts from raw data and write report.json
python3 /solution/oracle_repair.py

# 4. acceptance tests for the scorer
mkdir -p /app/workspace/acceptance_tests
cp /solution/acceptance_tests/*.py /app/workspace/acceptance_tests/
