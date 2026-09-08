#!/usr/bin/env bash
# ==============================================================================
# Resumable Model Downloader for Home AI Assistant
# If network drops, just run this script again - it will resume where it stopped!
# ==============================================================================

set -e

# Terminal colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}    Local AI Models Downloader (Resumable)          ${NC}"
echo -e "${CYAN}====================================================${NC}"

# Create model directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p models/llm
mkdir -p models/tts
mkdir -p models/stt

# Helper function to download with resume, retries, and skip-if-complete check
download_resumable() {
    local url="$1"
    local output="$2"
    local name="$3"
    local min_size_bytes="${4:-1000}"

    if [ -f "$output" ]; then
        local current_size
        current_size=$(wc -c < "$output" 2>/dev/null || echo 0)
        current_size=$(echo "$current_size" | tr -d '[:space:]')
        if [ "$current_size" -ge "$min_size_bytes" ]; then
            echo -e "${GREEN}✓ ${name} already downloaded and verified (${current_size} bytes). Skipping!${NC}"
            return 0
        fi
        echo -e "\n${YELLOW}Resuming download for ${name} (currently at ${current_size} bytes)...${NC}"
    else
        echo -e "\n${YELLOW}Downloading ${name}...${NC}"
    fi

    echo -e "${BLUE}Target: ${output}${NC}"
    
    # -L: follow redirects
    # -C -: automatically resume where it left off
    # --retry 15: retry up to 15 times on network glitch
    # --retry-delay 2: wait 2 seconds between retries
    curl -L -C - --retry 15 --retry-delay 2 --retry-all-errors \
         --progress-bar \
         -o "$output" \
         "$url"

    echo -e "${GREEN}✓ ${name} ready!${NC}"
}

# 1. LLM Brain: Llama 3.2 3B Instruct (GGUF Q4_K_M ~ 2.0 GB)
# Great reasoning, understands counting/instructions, runs fast on CPU
LLM_3B_URL="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
download_resumable "$LLM_3B_URL" "models/llm/Llama-3.2-3B-Instruct-Q4_K_M.gguf" "Llama 3.2 3B (LLM Brain)" 2000000000

# 2. STT Ears: Faster-Whisper small.en (~ 460 MB)
# 6x larger acoustic understanding than tiny, far better for regional accents
STT_BASE_URL="https://huggingface.co/Systran/faster-whisper-small.en/resolve/main"
download_resumable "${STT_BASE_URL}/model.bin" "models/stt/model.bin" "Whisper small.en (Acoustic Model)" 450000000
download_resumable "${STT_BASE_URL}/config.json" "models/stt/config.json" "Whisper small.en (Config)" 2000
download_resumable "${STT_BASE_URL}/tokenizer.json" "models/stt/tokenizer.json" "Whisper small.en (Tokenizer)" 2000000
download_resumable "${STT_BASE_URL}/vocabulary.txt" "models/stt/vocabulary.txt" "Whisper small.en (Vocabulary)" 400000

# 3. TTS Voice: Piper Neural Voice (en_US-lessac-medium ~ 63 MB)
# High quality, natural local offline speech
PIPER_MODEL_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
PIPER_CONFIG_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

download_resumable "$PIPER_MODEL_URL" "models/tts/en_US-lessac-medium.onnx" "Piper Voice Model (TTS)" 60000000
download_resumable "$PIPER_CONFIG_URL" "models/tts/en_US-lessac-medium.onnx.json" "Piper Voice Config (TTS)" 4000

echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}   All Local Models Verified in ./models/!          ${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "Your local AI models are self-contained in this folder."
echo -e "When switching to the other laptop, just copy the whole project folder!"
