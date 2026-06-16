#!/usr/bin/env bash
# One-shot local deployment: creates directories, starts containers, then wires services.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${SCRIPT_DIR}/scripts/setup.sh"
bash "${SCRIPT_DIR}/scripts/config.sh"
