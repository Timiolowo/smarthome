# Timilehin Home AI Assistant

A private, modular DIY Home AI Assistant designed to run on a home server laptop and act as the central brain of the house.

## Project Structure

```text
SmartHome/
├── setup.sh                 # One-step automated bootstrap script (macOS & Linux)
├── download_models.sh       # Resumable offline AI model downloader (LLM, STT, TTS)
├── requirements.txt         # Python dependencies (sounddevice, SpeechRecognition, colorama, pyttsx3)
├── config.json.example      # Configuration template
├── config.json              # Active local configuration
├── data/
│   ├── assistant.json       # AI Assistant's own identity, name, and behavior rules
│   ├── memory.json          # Timilehin's profile, boundaries & entertainment tastes
│   ├── state.json           # Live working household state (presence, media, power)
│   └── memory_log.jsonl     # Chronological episodic timeline of events
├── test_components.py       # Diagnostic check for presence, speaker, and microphone
├── Home_AI_Assistant_Project.md # High-level roadmap and project vision
├── models/                  # Self-contained offline AI models (LLM, TTS, STT)
└── src/
    ├── __init__.py
    ├── config.py            # Loads configuration from config.json
    ├── memory.py            # Dynamic multi-tier memory manager (profile, state, episodic log)
    ├── brain.py             # Local Llama 3.2 1B CPU inference engine
    ├── presence.py          # Network presence tracker with ICMP ping & ARP fallback
    ├── voice_output.py      # Cross-platform TTS (macOS 'say' / Linux pyttsx3 / espeak)
    ├── voice_input.py       # Offline Faster-Whisper STT & microphone voice activity detection
    └── main.py              # Phase 1 & 2 state machine & coordinator
```

## Quick Start (Foolproof 2 Commands)

### 1. Install Everything (All-in-One)
On **any laptop** (macOS or Linux / Raspberry Pi), just run:
```bash
./install.sh
```
*This automatically creates the virtual environment, installs Python packages, downloads all AI models (with auto-resume), and initializes configuration.*

### 2. Launch the Assistant
```bash
./run.sh
```
Or to test arrival immediately without waiting for phone Wi-Fi:
```bash
./run.sh --simulate-presence
```

## Configuration (`config.json`)

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
  "phrase_time_limit_seconds": 5
}
```

- **`phone_ip`**: The local IP address of your phone on your home Wi-Fi network (reserve this IP in your router's DHCP settings for reliability).
- **`presence_debounce_count`**: Number of consecutive missed pings before marking you as "Away" (prevents false departures when phones sleep).
- **`greeting_text`**: The phrase spoken aloud when you arrive and say "Hello".
- **`trigger_phrases`**: Spoken words that activate the greeting.

## Assistant Persona & Tone
- **Grounded & Chill**: Observant, helpful, and natural—like a sharp, reliable friend.
- **STRICT RULE**: Purely an assistant, **never a romantic AI**. No pet names (*no 'my love', 'my precious', 'sweetie', etc.*), no melodramatic speeches.
- **Concise**: Keeps responses tight (1–2 sentences) and focused on home comfort, entertainment (*Merlin*, *Silo*, *The 100*, *Alchemy of Souls*), and power status.
- **Smooth Speech Playback**: Assistant completes speaking without self-interruption from speaker echo.

## Moving to Another Laptop or Sharing with Someone Else

1. Copy or send this entire `SmartHome` folder to the other machine (flash drive, zip, or git).
2. On the new machine, open terminal in the folder and run:
   ```bash
   ./install.sh
   ```
   *(It automatically detects the OS, sets up the virtual environment, installs dependencies, and ensures local models are ready).*
3. Launch with:
   ```bash
   ./run.sh
   ```
