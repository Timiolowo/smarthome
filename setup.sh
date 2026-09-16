#!/usr/bin/env bash
# ==============================================================================
# Home AI Assistant - Automated Setup Script
# Works on macOS and Linux (Debian, Ubuntu, Raspberry Pi OS, etc.)
# ==============================================================================

set -e

# Terminal colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}    Home AI Assistant Setup & Installation    ${NC}"
echo -e "${BLUE}==============================================${NC}"

# 1. Detect Operating System
OS="$(uname -s)"
echo -e "\n${YELLOW}[1/5] Detecting Operating System...${NC}"
case "$OS" in
    Darwin)
        echo -e "System detected: ${GREEN}macOS ($(uname -m))${NC}"
        ;;
    Linux)
        echo -e "System detected: ${GREEN}Linux ($(uname -m))${NC}"
        # If Debian/Ubuntu, check for essential build headers if pip build is needed
        if command -v apt-get >/dev/null 2>&1; then
            echo "Debian/Ubuntu package manager detected."
            echo "Note: If audio libraries fail to install, you may need:"
            echo "  sudo apt-get update && sudo apt-get install -y python3-dev python3-venv portaudio19-dev libasound2-dev espeak"
        fi
        ;;
    *)
        echo -e "${YELLOW}Warning: Untested system ($OS). Proceeding with standard Python setup...${NC}"
        ;;
esac

# 2. Check for Python 3
echo -e "\n${YELLOW}[2/5] Checking Python installation...${NC}"
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY_VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
        if [ -n "$PY_VER" ]; then
            MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 9 ]; then
                PYTHON_CMD="$cmd"
                echo -e "Found Python: ${GREEN}$($cmd --version)${NC} ($cmd)"
                break
            fi
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: Python 3.9+ is required but was not found on your system.${NC}"
    echo "Please install Python 3.9 or higher and rerun this script."
    exit 1
fi

# 3. Create Virtual Environment
echo -e "\n${YELLOW}[3/5] Setting up virtual environment (.venv)...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment at $SCRIPT_DIR/.venv ..."
    "$PYTHON_CMD" -m venv .venv
else
    echo "Virtual environment (.venv) already exists."
fi

# Activate virtual environment
# shellcheck disable=SC1091
source .venv/bin/activate
echo -e "Active Python: ${GREEN}$(python --version)${NC} ($(which python))"

# 4. Install Dependencies
echo -e "\n${YELLOW}[4/5] Installing dependencies from requirements.txt...${NC}"
pip install --upgrade pip setuptools wheel

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}Error: requirements.txt not found!${NC}"
    exit 1
fi

# 5. Check Configuration File
echo -e "\n${YELLOW}[5/5] Checking configuration...${NC}"
if [ ! -f "config.json" ]; then
    if [ -f "config.json.example" ]; then
        cp config.json.example config.json
        echo -e "${GREEN}Created config.json from config.json.example.${NC}"
    else
        echo -e "${YELLOW}Warning: config.json.example not found.${NC}"
    fi
else
    echo -e "${GREEN}config.json exists.${NC}"
fi

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}Created .env from .env.example template.${NC}"
    else
        echo -e "${YELLOW}Warning: .env.example not found.${NC}"
    fi
else
    echo -e "${GREEN}.env exists (kept local and private).${NC}"
fi

echo -e "\n${GREEN}==============================================${NC}"
echo -e "${GREEN}             Setup Complete!                  ${NC}"
echo -e "${GREEN}==============================================${NC}"
echo -e "\n✨ Launch the Interactive Setup Wizard UI to configure your profile & models:"
echo -e "  ${CYAN}python setup.py${NC}"
echo -e "\nTo start the Home Assistant directly:"
echo -e "  ${BLUE}source .venv/bin/activate${NC}"
echo -e "  ${BLUE}python -m src.main${NC}\n"
