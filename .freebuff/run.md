# SmartHome — Preview Run Doc

Offline smart-home assistant: local LLM brain (llama.cpp), Faster-Whisper STT, macOS `say`/Piper TTS, and a dependency-free Python web dashboard.

## Artifacts a fresh checkout needs

- **Python env**: `./install.sh` (creates `.venv` and installs `requirements.txt`). No lockfile; stdlib-only web server, but the assistant needs `faster-whisper`, `llama-cpp-python`, `sounddevice`, etc.
- **Models (not in git)**: `./download_models.sh` fetches into `models/` — `llm/Llama-3.2-3B-Instruct-Q4_K_M.gguf` (~2 GB), `stt/model.bin` (Faster-Whisper small.en, ~461 MB), `tts/en_US-lessac-medium.onnx` (~60 MB). The dashboard's Overview page reads model sizes from disk and shows "Downloaded/Ready" per component.
- **Config**: `config.json` at repo root (copy/adapt from `config.json.example`). No `.env` files in this project; nothing secret to copy.
- **Data**: `data/memory.json`, `data/state.json` are created at runtime if missing.

## How to run

- **Dashboard only (what the Preview uses)** — from repo root:
  `.venv/bin/python -m src.web_server`
  Serves `web/index.html` plus `/api/*` on **port 5050** (auto-increments up to 5059 if busy). No build step, no node_modules.
- **Full assistant (voice loop + dashboard)**: `./run.sh` (equivalent to `python -m src.main`). Useful flags: `--web-only`, `--diagnose-audio`, `--list-microphones`.
- **Tests**: `.venv/bin/python -m unittest tests.test_audio tests.test_conversation`

### Run detached on this Mac (launchd)

`nohup ... &` gets reaped by the agent runner, and plain launchd jobs fail with exit 1 because TCC blocks Documents-folder access for spawn-on-demand jobs. Working recipe:

```sh
launchctl submit -l com.freebuff.preview-smarthome-f0156ceb -- /bin/sh -c \
  "cd /Users/timilehinlafe/Documents/Projects/SmartHome && exec $PWD/.venv/bin/python -m src.web_server > /tmp/smarthome-preview.log 2>&1"
```

Key details: log file must live outside `~/Documents` (e.g. `/tmp`), and the command must `cd` to the repo root (`python -m` needs it on `sys.path`). Startup takes ~30–60 s under launchd because importing `src.web_server` loads the GGUF brain before the port binds. Stop it with `launchctl remove com.freebuff.preview-smarthome-f0156ceb`.

### Known macOS gotcha

Running `src.main` (voice loop) from inside Freebuff's terminal silently gets **zero mic audio**: TCC denies `kTCCServiceMicrophone` for the Freebuff app (no audio-input entitlement) and never shows a prompt. `VoiceListener.calibrate()` now detects the all-zero stream and falls back to typed input with an explanatory error. The fix is launching `./run.sh` from the regular Terminal app and granting it microphone access.
