#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pip install -r environment/requirements.txt
python3 code/analysis/verify_paper_claims.py
python3 code/analysis/analyze_c2_envelope.py > results/c2/c2_envelope_recompute.json
python3 code/analysis/analyze_long_horizon.py > results/long_horizon/long_horizon_recompute.json
python3 code/analysis/generate_fig8_envelope.py
echo 'Primary anonymous checks complete.'
