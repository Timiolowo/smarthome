# Smart Home AI Assistant

[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/Timiolowo/smarthome)
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
- **Liquid Glass Web Dashboard & Setup Wizard**: Real-time web interface with visual configuration, live audio visualizers, and customizable themes.
- **Voice Barge-In & Interruption**: Instant cancellation of assistant speech when you speak or press wake buttons.

---

## Installation (Choose Your Preferred Method)

No coding experience is needed. Choose any installation method below:

### Option 1: 1-Line Terminal Install (No Git Required)

Paste and run one command in your terminal. It downloads the project, sets up dependencies, and initializes everything automatically:

**On macOS & Linux (Terminal):**
```bash
curl -fsSL https://github.com/Timiolowo/smarthome/archive/refs/heads/main.zip -o smarthome.zip && unzip -q smarthome.zip && cd smarthome-main && chmod +x install.sh run.sh && ./install.sh
```

**On Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri "https://github.com/Timiolowo/smarthome/archive/refs/heads/main.zip" -OutFile "smarthome.zip"; Expand-Archive -Path "smarthome.zip" -DestinationPath "."; cd smarthome-main; .\install.bat
```

---

### Option 2: Git Clone

```bash
# 1. Clone the repository
git clone https://github.com/Timiolowo/smarthome.git
cd smarthome

# 2. Run the installer
# On macOS & Linux:
chmod +x install.sh run.sh
./install.sh

# On Windows:
install.bat
```

---

## Easy Visual Setup (No Coding Required)

You do **not** need to edit JSON code or configuration files manually. 

When you start the assistant, open your browser to configure everything through the **Visual Setup Wizard**:

**`http://localhost:5050/setup`** (or run `python setup.py`)

The visual wizard guides you step-by-step through:
1. **User Profile & Persona**: Enter your name, preferred greeting, and assistant name.
2. **Phone Wi-Fi IP (Presence)**: Enter your phone's local Wi-Fi IP address (with built-in guide for iPhone and Android) so the assistant automatically greets you when you come home.
3. **AI Brain & Provider**: Choose between 100% offline local AI (Llama 3.2) with built-in live terminal download logs, or Cloud APIs (Groq, Gemini, OpenAI, Claude, DeepSeek) with a single click.
4. **Voice & Audio**: Select your preferred speaker voice and calibrate your microphone.

---

## How Presence Detection Works

The assistant knows when you arrive and leave your home without needing any mobile apps, GPS tracking, or battery drain on your phone:

1. **Automatic Wi-Fi Association**: When you return home and your smartphone connects to your local home Wi-Fi network, your router recognizes your device.
2. **Low-Latency Network Ping (Layer 1)**: The assistant periodically sends lightweight, non-intrusive network pings to your phone's local IP address.
3. **Hardware ARP Inspection Fallback (Layer 2)**: Modern iOS and Android devices enter deep sleep and ignore network pings when the screen is turned off. To prevent false departures, the assistant automatically inspects your router's local hardware ARP table (`arp -a` on Windows/macOS, `arp -n` on Linux). If your phone's MAC address is still associated with the Wi-Fi router, the system knows you are still at home.
4. **Debounce Engine (Anti-Flapping)**: Requires multiple consecutive missed cycles before marking you as "Away", ensuring temporary Wi-Fi blips or deep power-saving states never trigger false exit states.
5. **Welcome Sequence**: The moment presence transitions from `Away` to `Home`, the assistant initiates your custom welcome greeting (e.g. *"Welcome home, Timilehin. How was your day?"*) and opens an active listening window to hear your reply.

---

## Running the Assistant

Once installed, launch the assistant anytime with:

**On macOS & Linux:**
```bash
./run.sh
```

**On Windows:**
```cmd
run.bat
```
*(Or double-click `run.bat` in File Explorer).*

The dashboard will open automatically in your browser (default `http://localhost:5050` or `http://localhost:8000`).

### Extra Run Modes
- **Simulate Arrival Immediately** (test greeting without waiting for Wi-Fi):
  ```bash
  ./run.sh --simulate-presence
  ```
- **Run System Diagnostics**:
  ```bash
  python test_components.py
  ```

---

## Architecture & Project Structure

```text
SmartHome/
├── install.sh                  # All-in-one automated installer (macOS & Linux)
├── install.bat                 # All-in-one automated installer (Windows)
├── run.sh                      # One-command launcher (macOS & Linux)
├── run.bat                     # One-command launcher (Windows)
├── download_models.sh          # Offline AI model downloader (macOS & Linux)
├── download_models.bat         # Offline AI model downloader (Windows)
├── requirements.txt            # Python dependencies
├── config.json.example         # Configuration template
├── config.json                 # Active local configuration (created automatically)
├── .env.example                # Cloud API keys template
├── test_components.py          # Diagnostic test suite for hardware & modules
├── models/                     # Offline AI models directory (Llama 3.2, Whisper, Piper)
├── data/                       # Persistent memory, state, and conversation logs
├── native/
│   └── VoiceAudio.swift        # macOS native audio capture driver
├── scripts/
│   └── request_mic_permission.sh # Helper script for macOS microphone access
├── src/                        # Core Python application logic
│   ├── main.py                 # Application entrypoint & coordinator
│   ├── agent.py                # Reasoning loop, intent classification & tool dispatcher
│   ├── brain.py                # LLM router & provider interface
│   ├── llm_providers.py        # Connectors for Groq, Gemini, OpenAI, Claude, Ollama, etc.
│   ├── memory.py               # Multi-tier memory manager
│   ├── presence.py             # Cross-platform network presence tracker (ping & ARP)
│   ├── voice_input.py          # Microphone listener, STT, and voice activity detection
│   ├── voice_output.py         # TTS engine & audio playback coordinator
│   ├── web_server.py           # Dashboard HTTP server & JSON REST API (with auto-port fallback)
│   ├── setup_wizard.py         # Visual setup onboarding server
│   ├── tools.py                # Smart home tools & automations
│   ├── routines.py             # Scheduled routines and triggers
│   ├── system_power.py         # Voice-controlled standby & wake management
│   ├── downloader.py           # Cross-platform model downloader engine
│   └── interruption.py         # Speech barge-in & cancellation hooks
└── web/                        # Web Dashboard frontend (HTML/CSS/JS)
    ├── index.html              # Main glassmorphic dashboard
    ├── setup.html              # Visual onboarding & model management UI
    ├── css/                    # Liquid glass stylesheets & visualizer themes
    ├── js/                     # Audio visualizers, chat & real-time sync
    └── components/             # Modular dashboard views (Home, Devices, Routines, Voice)
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
- **Windows**: Ensure microphone permissions are enabled in *Windows Settings > Privacy & Security > Microphone*.
- **Web UI**: Ensure browser microphone permissions are allowed when prompted.

### 2. Port already in use (Automatic Port Fallback)
The web server **automatically detects busy ports** and binds to the next open port (e.g. 5050 -> 5051 -> 5052...) without crashing. The active URL is displayed in your terminal output and opened automatically in your browser.

### 3. Phone presence always shows "Away"
- Ensure your phone is connected to the same local 2.4/5GHz Wi-Fi network.
- Check your phone's IP in *Settings > Wi-Fi* and enter it in the Setup Wizard (`http://localhost:5050/setup`).
- If your phone uses Private Wi-Fi MAC addresses, toggle your home Wi-Fi connection setting to **Use Device MAC**.

---

<details>
<summary><b>Advanced: Manual Configuration (Optional)</b></summary>

If you prefer to edit configuration files manually instead of using the Visual Setup Wizard:

1. **`config.json`**:
```json
{
  "user_name": "Timilehin",
  "phone_ip": "192.168.18.3",
  "presence_poll_interval_seconds": 5,
  "presence_debounce_count": 2,
  "greeting_text": "Welcome home, Timilehin!",
  "trigger_phrases": ["hello", "hey", "hi"],
  "voice_name": "Samantha",
  "listen_timeout_seconds": 7,
  "phrase_time_limit_seconds": 5,
  "conversation_timeout_seconds": 30,
  "conversation_phrase_limit_seconds": 25,
  "microphone_device": null,
  "echo_cancellation": true,
  "ready_chime": false,
  "llm_provider": "local"
}
```

2. **`.env`** (for Cloud LLM API Keys):
```bash
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_claude_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```
</details>

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
