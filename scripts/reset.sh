#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git restore --source=HEAD --worktree -- consumers/ parity/report_spec.yaml
find parity/baseline -type f ! -name .gitkeep -delete
.venv/bin/python parity/run_baseline.py
