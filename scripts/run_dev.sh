#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
uv run python -m meshtastic_llm_bridge
