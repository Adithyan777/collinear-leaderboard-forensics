#!/bin/bash
# Verifier entrypoint. Ground truth lives under /tests (mounted at verify
# time only). Writes /logs/verifier/reward.json.
mkdir -p /logs/verifier
python3 /tests/grader/main.py --workspace /app/workspace \
  --out /logs/verifier/reward.json 2> /logs/verifier/grader_stderr.log
if [ ! -f /logs/verifier/reward.json ]; then
  echo '{"overall": 0.0, "root_cause_fix": 0.0, "data_repair": 0.0, "report_accuracy": 0.0, "test_suite": 0.0}' > /logs/verifier/reward.json
fi
