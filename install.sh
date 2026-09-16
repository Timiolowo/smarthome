#!/usr/bin/env bash
# ==============================================================================
# Smart Home AI Assistant - Complete All-in-One Installer
# Works out-of-the-box on any new laptop (macOS & Linux / Raspberry Pi)
# ==============================================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN}    🏡 Smart Home AI Assistant - All-in-One Setup     ${NC}"
echo -e "${CYAN}======================================================${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Detect Operating System
OS="$(uname -s)"
echo -e "\n${YELLOW}[Step 1/5] Detecting System Architecture...${NC}"
case "$OS" in
    Darwin)
        echo -e "Operating System: ${GREEN}macOS ($(uname -m))${NC}"
        ;;
    Linux)
        echo -e "Operating System: ${GREEN}Linux ($(uname -m))${NC}"
        if command -v apt-get >/dev/null 2>&1; then
            echo -e "${BLUE}Debian/Ubuntu package manager found.${NC}"
        fi
        ;;
    *)
        echo -e "${YELLOW}Warning: Untested environment ($OS). Attempting standard setup...${NC}"
        ;;
esac

# 2. Check for Python 3.9+
echo -e "\n${YELLOW}[Step 2/5] Checking Python Version...${NC}"
PYTHON_BIN=""
for cmd in python3.11 python3.10 python3.12 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY_VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
        if [ -n "$PY_VER" ]; then
            MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 9 ]; then
                PYTHON_BIN="$cmd"
                echo -e "Found compatible Python: ${GREEN}$($cmd --version)${NC} ($cmd)"
                break
            fi
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}Error: Python 3.9 or higher is required.${NC}"
    echo "Please install Python 3.9+ and run this script again."
    exit 1
fi

# 3. Create and Activate Virtual Environment
echo -e "\n${YELLOW}[Step 3/5] Configuring Python Virtual Environment (.venv)...${NC}"
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment at $SCRIPT_DIR/.venv ..."
    "$PYTHON_BIN" -m venv .venv
else
    echo "Virtual environment (.venv) already exists."
fi

# shellcheck disable=SC1091
source .venv/bin/activate
echo -e "Active Python: ${GREEN}$(python --version)${NC} in $(which python)"

echo -e "\nInstalling & updating dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Initialize Data & Config Directories
echo -e "\n${YELLOW}[Step 4/5] Initializing Configuration & Memory Storage...${NC}"
mkdir -p data models/llm models/tts models/stt

if [ ! -f "config.json" ]; then
    if [ -f "config.json.example" ]; then
        cp config.json.example config.json
        echo -e "${GREEN}Created config.json from template.${NC}"
    fi
else
    echo -e "${GREEN}config.json found.${NC}"
fi

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}Created local .env from .env.example template.${NC}"
    fi
else
    echo -e "${GREEN}.env found (kept local and private).${NC}"
fi

# 5. Check & Download Local AI Models (if missing)
echo -e "\n${YELLOW}[Step 5/5] Checking Local Offline AI Models...${NC}"
LLM_3B="models/llm/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
LLM_1B="models/llm/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
STT_FILE="models/stt/model.bin"
TTS_FILE="models/tts/en_US-lessac-medium.onnx"

if { [ ! -f "$LLM_3B" ] && [ ! -f "$LLM_1B" ]; } || [ ! -f "$STT_FILE" ] || [ ! -f "$TTS_FILE" ]; then
    echo -e "${BLUE}Local model files not found or incomplete. Verifying/downloading them now...${NC}"
    ./download_models.sh
else
    echo -e "${GREEN}All local models are present in ./models/!${NC}"
fi

# Make run.sh executable
chmod +x run.sh 2>/dev/null || true

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}        🎉 Setup Completed Successfully!             ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "To start your Home AI Assistant, just run:"
echo -e "   ${CYAN}./run.sh${NC}"
echo -e "Or to test arrival immediately without waiting for Wi-Fi:"
echo -e "   ${CYAN}./run.sh --simulate-presence${NC}\n"
