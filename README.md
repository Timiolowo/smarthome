# Smart Home AI Assistant

[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Raspberry%20Pi-0078D6?style=flat-square&logo=apple&logoColor=white)](https://github.com/Timiolowo/smarthome)
[![Architecture](https://img.shields.io/badge/Local%20First-Llama%203.2%20%2B%20Whisper-FF6B6B?style=flat-square&logo=meta&logoColor=white)](https://github.com/Timiolowo/smarthome)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

A private, modular, local-first DIY Home AI Assistant designed to run on a home server laptop or mini PC and act as the intelligent central brain of your living space.

---

## Key Features

- **Multi-Provider Intelligence**: Run 100% offline with local GGUF models (Llama 3.2 1B/3B via `llama.cpp`) or connect to ultra-fast cloud providers (Groq, Google Gemini, OpenAI, Anthropic Claude, DeepSeek, Ollama, OpenRouter, Mistral, LM Studio).
- **Natural Voice Stack**: Offline speech-to-text via Faster-Whisper, real-time microphone voice activity detection (VAD), and flexible text-to-speech (macOS `say`, Piper TTS, pyttsx3, and browser Web Speech).
- **Passive Presence Detection**: Automatic arrival and departure awareness via Wi-Fi network polling (ICMP ping & ARP fallback) without draining phone battery or requiring a mobile companion app.
- **Multi-Tier Dynamic Memory**: 
  - `assistant.json`: AI persona, personality traits, and operational guidelines.
  - `memory.json`: User profile, favorite entertainment, schedules, routines, and boundaries.
  - `state.json`: Live household state (presence, media, alarms, power, active UI view).
  - `memory_log.jsonl`: Chronological episodic timeline of conversations and trigger events.
- **Smart Home Tool Execution**: Built-in tool calling for media playback, alarms, timers, weather, routines, UI themes, visual engines, and system power management.
- **Liquid Glass Web Dashboard**: Real-time web interface (`http://localhost:8000`) featuring:
  - Dynamic visualizer engines (Particle Wave, Neural Network, Sound Sphere, Hologram, Matrix Rain, Starlight).
  - Customizable UI themes (Liquid Glass, Cyberpunk, Obsidian, Solar Gold, Frost Neo, Cyber Glass, Aurora Dark).
  - Interactive Voice Hub with browser audio streaming, wake word control, and live state sync.
  - Setup wizard and offline model downloader.
- **Voice Barge-In & Interruption**: Instant cancellation of assistant speech when you speak or press wake buttons.

---

## Architecture & Project Structure

```text
SmartHome/
├── install.sh                  # All-in-one automated installer (macOS & Linux)
├── setup.sh                    # Automated setup & environment verification
├── run.sh                      # One-command runtime launcher
├── download_models.sh          # Resumable offline AI model downloader (LLM, STT, TTS)
├── requirements.txt            # Python dependencies
├── config.json.example         # Configuration template
├── config.json                 # Active local configuration (created during setup)
├── .env.example                # Environment variables template for API keys
├── test_components.py          # Diagnostic test suite for hardware & modules
├── models/                     # Offline AI models directory
│   ├── llm/                    # Quantized GGUF models (e.g. Llama-3.2-1B / 3B)
│   ├── stt/                    # Faster-Whisper STT model
│   └── tts/                    # Piper TTS voice models & configs
├── data/                       # Persistent JSON memory and state files
│   ├── assistant.json          # Assistant persona & identity
│   ├── memory.json             # User profile, habits, entertainment preferences
│   ├── state.json              # Real-time working state & device statuses
│   └── memory_log.jsonl        # Chronological conversation & action history
├── native/
│   └── VoiceAudio.swift        # macOS native audio capture driver
├── scripts/
│   └── request_mic_permission.sh # Helper script for macOS microphone access
├── src/                        # Core Python application logic
│   ├── main.py                 # Application entrypoint & coordinator
│   ├── agent.py                # Reasoning loop, intent classification & tool dispatcher
│   ├── brain.py                # LLM router & provider interface
│   ├── llm_providers.py        # Connectors for Groq, Gemini, OpenAI, Claude, Ollama, etc.
│   ├── memory.py               # Long-term, short-term, and episodic memory manager
│   ├── presence.py             # Network presence tracker (ping & ARP)
│   ├── voice_input.py          # Microphone listener, STT, and voice activity detection
│   ├── voice_output.py         # TTS engine & audio playback coordinator
│   ├── web_server.py           # Dashboard HTTP server & JSON REST API
│   ├── tools.py                # Executable smart home tools & automations
│   ├── routines.py             # Scheduled routines and triggers
│   ├── system_power.py         # Voice-controlled standby & wake management
│   ├── downloader.py           # Model downloader engine with resume support
│   └── interruption.py         # Speech barge-in & cancellation hooks
└── web/                        # Web Dashboard frontend (Vanilla HTML/CSS/JS)
    ├── index.html              # Main glassmorphic dashboard
    ├── setup.html              # First-time onboarding & model management UI
    ├── css/                    # Liquid glass stylesheets & visualizer themes
    ├── js/                     # Client-side audio visualizers, chat & WebSocket/polling
    └── components/             # Modular dashboard views (Home, Devices, Routines, Voice)
```

---

## Prerequisites

Before installing, ensure your host system has:

- **Operating System**: macOS (Apple Silicon / Intel) or Linux (Debian, Ubuntu, Raspberry Pi OS 64-bit).
- **Python**: Version `3.9` to `3.12` installed (`python3 --version`).
- **Audio Hardware**: Working microphone and speakers / headphones.
- **Git**: Installed on your system (`git --version`).
- **Network Tools** *(Linux only)*: `iputils-ping`, `portaudio19-dev`, `ffmpeg`, and `libasound2-dev`.

---

## Step-by-Step Installation Guide

### Method 1: Automated All-in-One Setup (Recommended)

The installer automatically detects your OS, creates a Python virtual environment, installs dependencies, initializes local configuration and environment files, and verifies offline AI models:

```bash
# 1. Clone the repository
git clone https://github.com/Timiolowo/smarthome.git
cd smarthome

# 2. Make installer executable and run it
chmod +x install.sh
./install.sh
```

---

### Method 2: Manual Step-by-Step Setup

#### Step 1: Install System Dependencies (Linux / Raspberry Pi)
On macOS, standard Xcode Command Line Tools (`xcode-select --install`) are sufficient. On Debian/Ubuntu/Raspberry Pi:
```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip portaudio19-dev ffmpeg libportaudio2 libasound2-dev espeak
```

#### Step 2: Create and Activate Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 3: Install Python Dependencies
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

#### Step 4: Initialize Configuration Files
```bash
# Copy example configuration (local only, ignored by Git)
cp config.json.example config.json

# Copy example environment variables (local only, ignored by Git)
cp .env.example .env
```

#### Step 5: Download Offline AI Models
Run the automated downloader to fetch the offline speech-to-text, text-to-speech, and local LLM models:
```bash
chmod +x download_models.sh
./download_models.sh
```
*Note: You can also download or change models later directly from the Web Dashboard at `http://localhost:8000/setup.html`.*

#### Step 6: Grant Microphone Permissions (macOS Only)
If running in macOS Terminal / iTerm2, grant microphone permissions:
```bash
chmod +x scripts/request_mic_permission.sh
./scripts/request_mic_permission.sh
```

---

## Configuration (`config.json` & `.env`)

### 1. `config.json` Settings

Edit `config.json` to customize your personal setup:

```json
{
  "user_name": "Timilehin",
  "phone_ip": "192.168.1.150",
  "presence_poll_interval_seconds": 5,
  "presence_debounce_count": 2,
  "greeting_text": "Welcome home, Timilehin. How was your day?",
  "trigger_phrases": ["hello", "hey", "hi"],
  "voice_name": "Samantha",
  "listen_timeout_seconds": 7,
  "phrase_time_limit_seconds": 5,
  "conversation_timeout_seconds": 30,
  "conversation_phrase_limit_seconds": 25,
  "microphone_device": null,
  "echo_cancellation": true,
  "ready_chime": false,
  "llm_provider": "local",
  "llm_model": null,
  "llm_api_key": null,
  "llm_base_url": null
}
```

| Setting | Description |
| :--- | :--- |
| `user_name` | Your name (used for personalized memory and greetings). |
| `phone_ip` | Static or DHCP-reserved local IP of your mobile phone on home Wi-Fi. |
| `presence_debounce_count` | Number of consecutive failed pings required before registering "Away" state. |
| `trigger_phrases` | Spoken activation keywords when greeted upon arrival. |
| `llm_provider` | Active LLM backend: `"local"`, `"groq"`, `"gemini"`, `"openai"`, `"anthropic"`, `"ollama"`, `"deepseek"`, `"openrouter"`, `"mistral"`, or `"lm_studio"`. |
| `voice_name` | System TTS voice name (e.g. `"Samantha"` on macOS). |

### 2. Cloud LLM API Keys (`.env`)

To use cloud LLM providers, add your API keys to `.env` or configure them directly in the Web UI:

```bash
# Cloud LLM API Keys
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_claude_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

---

## Running the Assistant

### 1. Standard Run
Start the full stack (core assistant loop, background presence monitor, and web server):
```bash
./run.sh
```
Open your browser at:
**`http://localhost:8000`**

### 2. Simulate Presence (Arrival Testing)
Test arrival greetings and presence workflows immediately without waiting for a phone to connect to Wi-Fi:
```bash
./run.sh --simulate-presence
```

### 3. Run Hardware & Component Diagnostics
Run the diagnostic suite to verify microphone, speaker, presence ping, memory, and LLM:
```bash
source .venv/bin/activate
python test_components.py
```

---

## Voice Commands & Capabilities

The assistant recognizes natural language commands and executes tools automatically:

- **Conversations & Knowledge**: "What's the weather like today?", "Who is Arthur Pendragon?", "Summarize what we discussed yesterday."
- **Media Control**: "Play chill music on Spotify", "Pause playback", "Set volume to 70%."
- **Timers & Alarms**: "Set a timer for 15 minutes for pasta", "Set an alarm for 7:30 AM tomorrow."
- **Dashboard & UI**: "Switch theme to Cyberpunk", "Change visualizer to Neural Network", "Turn on kiosk mode."
- **Power & System**: "Go to sleep", "Power off voice core."

---

## Troubleshooting & FAQs

### 1. Microphone not picking up voice
- **macOS**: Make sure Terminal / iTerm2 has Microphone access under *System Settings > Privacy & Security > Microphone*. Run `./scripts/request_mic_permission.sh` to trigger the permission prompt.
- **Linux**: Check available devices with `python -c "import sounddevice; print(sounddevice.query_devices())"`. Set `"microphone_device"` index in `config.json` if needed.
- **Web UI**: Ensure browser microphone permissions are enabled for `http://localhost:8000`.

### 2. Port 8000 already in use
If another process is using port 8000, find and terminate it:
```bash
lsof -ti :8000 | xargs kill -9
```

### 3. Phone presence always shows "Away"
- Verify your phone is connected to the same local 2.4/5GHz Wi-Fi network subnet.
- Configure DHCP reservation / static IP for your phone in your home router settings.
- Some newer phones randomize Wi-Fi MAC/IP addresses; set your home Wi-Fi network setting on your phone to **Use Device MAC**.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
