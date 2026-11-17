#!/usr/bin/env bash
# Run every bot's end-to-end scenario on the offline Telegram emulator, then rebuild screenshots.
set -euo pipefail
cd "$(dirname "$0")/.."
for s in booking leads ai; do python "demo/scenario_$s.py"; done
python demo/render.py
node demo/screenshot.mjs
