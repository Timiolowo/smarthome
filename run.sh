#!/usr/bin/env bash
# ==============================================================================
# 1-Click Launcher for Timilehin Home AI Assistant
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Running installer first..."
    ./install.sh
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m src.main "$@"
