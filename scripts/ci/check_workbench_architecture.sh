#!/usr/bin/env bash
set -euo pipefail

python3 "$(cd "$(dirname "$0")" && pwd)/check_workbench_architecture.py"

