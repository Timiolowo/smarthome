import json
import os
import platform
import re
import shutil
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from src.agent import agent
from src.brain import brain
from src.config import load_config
from src.memory import memory
from src.tools import tools, play_alarm_sound
from src import audio_runtime
from src.downloader import downloader, MODEL_SPECS, get_system_hardware_specs
from src.interruption import response_interruption
from src.system_power import system_power
from src.browser_voice import browser_voice

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
MEMORY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "memory.json")
STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "state.json")
ASSISTANT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "assistant.json")
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")


def get_system_status():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass

    assistant_info = {}
    if os.path.exists(ASSISTANT_PATH):
        try:
            with open(ASSISTANT_PATH, "r", encoding="utf-8") as f:
                assistant_info = json.load(f)
        except Exception:
            pass

    mem = {}
    if os.path.exists(MEMORY_PATH):
        try:
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                mem = json.load(f)
        except Exception:
            pass

    state = {}
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass

    # Check model statuses
    llm_3b = os.path.join(MODELS_DIR, "llm", "Llama-3.2-3B-Instruct-Q4_K_M.gguf")
    llm_1b = os.path.join(MODELS_DIR, "llm", "Llama-3.2-1B-Instruct-Q4_K_M.gguf")
    stt_bin = os.path.join(MODELS_DIR, "stt", "model.bin")
    tts_onnx = os.path.join(MODELS_DIR, "tts", "en_US-lessac-medium.onnx")

    def file_info(path, target_size=1):
        if os.path.exists(path):
            sz = os.path.getsize(path)
            complete = sz >= target_size
            return {"exists": True, "size_bytes": sz, "complete": complete}
        return {"exists": False, "size_bytes": 0, "complete": False}

    models_info = {
        "llm_3b": file_info(llm_3b, 2_000_000_000),
        "llm_1b": file_info(llm_1b, 750_000_000),
        "stt": file_info(stt_bin, 450_000_000),
        "tts": file_info(tts_onnx, 60_000_000),
    }

    active_timers = tools.get_active_timers()
    active_reminders = tools.get_active_reminders()
    assistant_runtime = state.get("assistant_runtime", {
        "state": "IDLE",
        "last_heard": "",
        "last_reply": "",
        "updated_at": datetime.now().isoformat(),
    })

    from src.browser_voice import browser_voice
    return {
        "config": cfg,
        "assistant": assistant_info,
        "app_knowledge": memory.load_app_knowledge(),
        "memory": mem,
        "state": state,
        "models": models_info,
        "stt_status": browser_voice.status(),
        "llm_provider": {
            "provider": brain.provider_name,
            "model": brain.model_name,
            "available": brain.available,
            "capabilities": brain.provider_capabilities,
        },
        "active_timers": len(active_timers),
        "active_timers_list": active_timers,
        "active_reminders": len(active_reminders),
        "active_reminders_list": active_reminders,
        "assistant_runtime": assistant_runtime,
        "ui": state.get("ui", {
            "theme": "midnight",
            "visual_engine": "2d",
            "active_tab": "tab-livedisplay",
            "kiosk_mode": False,
        }),
        "voice_audio": audio_runtime.snapshot(),
        "system_power": system_power.status(),
        "downtime": {
            "active_sleep": state.get("downtime", {}).get("active_sleep"),
            "last_downtime_seconds": state.get("downtime", {}).get("last_downtime_seconds", 0),
        },
        "active_sleep": state.get("downtime", {}).get("active_sleep"),
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


class AssistantRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, filepath, content_type="text/html"):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        with open(filepath, "rb") as f:
            content = f.read()

        # Dynamic recursive component inclusion for modular development
        if "html" in content_type and b"<!-- include" in content:
            text = content.decode("utf-8")
            base_dir = os.path.abspath(os.path.dirname(filepath))

            def expand_includes(raw_text, current_dir, depth=0):
                if depth > 10 or "<!-- include" not in raw_text:
                    return raw_text

                def replacer(match):
                    inc_rel = match.group(1).strip("\"' ")
                    # Allow resolving relative to current component directory or WEB_DIR root
                    candidates = [
                        os.path.abspath(os.path.join(current_dir, inc_rel)),
                        os.path.abspath(os.path.join(WEB_DIR, inc_rel))
                    ]
                    for inc_path in candidates:
                        if os.path.exists(inc_path) and os.path.commonpath([WEB_DIR, inc_path]) == WEB_DIR:
                            try:
                                with open(inc_path, "r", encoding="utf-8") as inc_f:
                                    child_content = inc_f.read()
                                return expand_includes(child_content, os.path.dirname(inc_path), depth + 1)
                            except Exception:
                                pass
                    return match.group(0)

                return re.sub(r'<!--\s*include\s+["\']?([^"\'>]+)["\']?\s*-->', replacer, raw_text)

            text = expand_includes(text, base_dir)
            content = text.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            from src.setup_wizard import is_first_time_setup
            if is_first_time_setup():
                self.send_response(302)
                self.send_header("Location", "/setup")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return
            index_file = os.path.join(WEB_DIR, "index.html")
            self._send_file(index_file, "text/html")
        elif path in ("/setup", "/setup.html"):
            setup_file = os.path.join(WEB_DIR, "setup.html")
            if os.path.exists(setup_file):
                self._send_file(setup_file, "text/html")
            else:
                self._send_file(os.path.join(WEB_DIR, "index.html"), "text/html")
        elif path in ("/test_voices", "/test_voices.html"):
            tv_file = os.path.join(WEB_DIR, "test_voices.html")
            if os.path.exists(tv_file):
                self._send_file(tv_file, "text/html")
            else:
                self._send_file(os.path.join(WEB_DIR, "index.html"), "text/html")
        elif path in ("/voice", "/home", "/chat", "/settings", "/actions", "/alarms", "/profile", "/ai"):
            # SPA client-side routes — serve index.html, JS reads the path
            index_file = os.path.join(WEB_DIR, "index.html")
            self._send_file(index_file, "text/html")
        elif path == "/api/status":
            self._send_json(get_system_status())
        elif path == "/api/reminders":
            rems = tools.get_active_reminders()
            self._send_json({"ok": True, "reminders": rems, "count": len(rems)})
        elif path == "/api/setup/status":
            cfg = {}
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                except Exception:
                    pass
            assistant_info = memory.load_assistant()
            models_status = downloader.get_models_status()
            devices = []
            try:
                import sounddevice as sd
                devices = [{"id": i, "name": d["name"]} for i, d in enumerate(sd.query_devices())
                           if d["max_input_channels"] > 0]
            except Exception:
                pass

            self._send_json({
                "setup_completed": cfg.get("setup_completed", False),
                "config": cfg,
                "assistant": assistant_info,
                "models": models_status,
                "system_specs": get_system_hardware_specs(),
                "audio_devices": devices,
            })
        elif path == "/api/models/download-status":
            self._send_json(downloader.get_download_status())
        elif path == "/api/audio-devices":
            try:
                import sounddevice as sd
                devices = [{"id": i, "name": d["name"]} for i, d in enumerate(sd.query_devices())
                           if d["max_input_channels"] > 0]
                self._send_json({"devices": devices})
            except Exception as exc:
                self._send_json({"devices": [], "error": str(exc)})
        elif path == "/api/events":
            qs = parse_qs(parsed.query)
            try:
                limit = int(qs.get("limit", [50])[0])
            except Exception:
                limit = 50
            category = qs.get("category", [None])[0]
            events = memory.get_recent_logs(limit=limit, category=category)
            self._send_json({"ok": True, "events": events})
        elif path == "/api/test-chime":
            threading.Thread(target=play_alarm_sound, args=(2,), daemon=True).start()
            self._send_json({"ok": True, "message": "Chime triggered"})
        elif path == "/api/system/power":
            self._send_json(system_power.status())
        elif path == "/api/system/health":
            from src.platform_adapter import platform_adapter
            from src.device_inventory import device_inventory
            self._send_json({
                "ok": True,
                "metrics": platform_adapter.get_system_metrics(),
                "battery": platform_adapter.get_battery_status(),
                "wifi": platform_adapter.get_wifi_status(),
                "devices": device_inventory.list_devices(),
            })
        elif path == "/api/android/status":
            from src.android_bridge import android_bridge
            self._send_json(android_bridge.get_phone_status())
        elif path == "/api/routines":
            from src.routines import routine_engine
            self._send_json({"ok": True, "routines": routine_engine.routines})
        elif path == "/api/notifications":
            from src.supervisor import supervisor
            self._send_json({"ok": True, "notifications": supervisor.get_notifications()})
        elif path == "/api/devices":
            from src.device_inventory import device_inventory
            self._send_json({"ok": True, "devices": device_inventory.list_devices()})
        elif path == "/api/knowledge":
            self._send_json({"ok": True, "knowledge": memory.load_app_knowledge()})
        elif path == "/api/terminal/logs":
            from src.terminal_logger import terminal_logger
            qs = parse_qs(parsed.query)
            try:
                limit = int(qs.get("limit", [100])[0])
            except Exception:
                limit = 100
            try:
                since_id = int(qs.get("since_id", [0])[0]) if "since_id" in qs else None
            except Exception:
                since_id = None
            self._send_json({"ok": True, "logs": terminal_logger.get_logs(limit=limit, since_id=since_id)})
        elif path == "/api/tts":
            qs = parse_qs(parsed.query)
            text = qs.get("text", [""])[0].strip()
            voice_param = qs.get("voice", [None])[0]
            if not text:
                self._send_json({"error": "No text provided"}, status=400)
                return

            import tempfile, subprocess
            from src.voice_output import SIRI_SWIFT_PATH, normalize_voice_name
            norm_v = normalize_voice_name(voice_param)

            cache_key = (norm_v, text)
            global _TTS_CACHE
            if "_TTS_CACHE" not in globals():
                _TTS_CACHE = {}

            wav_bytes = _TTS_CACHE.get(cache_key)

            if not wav_bytes and platform.system().lower() == "darwin" and shutil.which("swift") and os.path.exists(SIRI_SWIFT_PATH):
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                        temp_path = tf.name
                    cmd = ["swift", SIRI_SWIFT_PATH, "-o", temp_path]
                    if norm_v:
                        cmd += ["-v", norm_v]
                    cmd.append(text)
                    res = subprocess.run(cmd, capture_output=True, timeout=20)
                    if res.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 100:
                        with open(temp_path, "rb") as f:
                            wav_bytes = f.read()
                        if len(_TTS_CACHE) < 120:
                            _TTS_CACHE[cache_key] = wav_bytes
                    if os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[TTS Endpoint] Siri Swift render error: {e}")

            if not wav_bytes and platform.system().lower() == "darwin" and not shutil.which("swift") and shutil.which("say"):
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                        temp_path = tf.name
                    cmd = ["say", "-o", temp_path, "--file-format=WAVE", "--data-format=LEI16@16000"]
                    if norm_v:
                        cmd += ["-v", norm_v]
                    cmd.append(text)
                    res = subprocess.run(cmd, capture_output=True, timeout=20)
                    if res.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 100:
                        with open(temp_path, "rb") as f:
                            wav_bytes = f.read()
                    if os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[TTS Endpoint] say render error: {e}")

            if not wav_bytes and platform.system().lower() == "windows":
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                        temp_path = tf.name
                    escaped_text = text.replace("'", "''")
                    escaped_path = temp_path.replace("'", "''")
                    ps_cmd = (
                        f"Add-Type -AssemblyName System.Speech; "
                        f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        f"$synth.SetOutputToWaveFile('{escaped_path}'); "
                        f"$synth.Speak('{escaped_text}'); "
                        f"$synth.Dispose()"
                    )
                    res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], capture_output=True, timeout=20)
                    if res.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 100:
                        with open(temp_path, "rb") as f:
                            wav_bytes = f.read()
                    if os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[TTS Endpoint] Windows PowerShell render error: {e}")

            if wav_bytes:
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(wav_bytes)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(wav_bytes)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass  # Client cancelled or interrupted audio stream early
            else:
                self._send_json({"error": "TTS synthesis failed"}, status=500)
        else:
            # Check for static files under WEB_DIR (css, js, icons, etc.)
            clean_rel = os.path.normpath(path.lstrip("/"))
            target_path = os.path.abspath(os.path.join(WEB_DIR, clean_rel))
            if os.path.isfile(target_path) and os.path.commonpath([WEB_DIR, target_path]) == WEB_DIR:
                ext = os.path.splitext(target_path)[1].lower()
                mimes = {
                    ".html": "text/html",
                    ".css": "text/css",
                    ".js": "application/javascript",
                    ".json": "application/json",
                    ".svg": "image/svg+xml",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".ico": "image/x-icon",
                    ".woff2": "font/woff2",
                    ".woff": "font/woff",
                    ".ttf": "font/ttf",
                }
                c_type = mimes.get(ext, "text/plain")
                self._send_file(target_path, c_type)
                return

            # Fallback to index.html for SPA routing
            index_file = os.path.join(WEB_DIR, "index.html")
            self._send_file(index_file, "text/html")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        if length > 3_000_000:
            self._send_json({"error": "Request is too large"}, status=413)
            return
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        if path == "/api/system/power":
            action = body.get("action", "toggle")
            from src.supervisor import supervisor
            if action == "on":
                supervisor.cancel_sleep()
                result = system_power.power_on()
            elif action == "off":
                result = system_power.power_off()
            elif action == "toggle":
                if not system_power.is_powered_on():
                    supervisor.cancel_sleep()
                result = system_power.toggle()
            else:
                self._send_json({"error": "action must be 'on', 'off', or 'toggle'"}, status=400)
                return
            self._send_json(result)
        elif path == "/api/voice/interrupt":
            from src.voice_output import stop
            generation_was_active = response_interruption.interrupt()
            stop()
            self._send_json({"ok": True, "generation_was_active": generation_was_active})
        elif path == "/api/terminal/clear":
            from src.terminal_logger import terminal_logger
            terminal_logger.clear()
            self._send_json({"ok": True, "message": "Terminal logs cleared"})
        elif path == "/api/terminal/command":
            cmd = body.get("command", "").strip()
            if not cmd:
                self._send_json({"error": "No command provided"}, status=400)
                return
            from src.agent import agent
            reply = agent.process_message(cmd)
            self._send_json({"ok": True, "command": cmd, "reply": reply})
        elif path == "/api/voice/listening":
            mode = body.get("mode", "").strip().lower()
            result = system_power.set_voice_mode(mode)
            self._send_json(result, status=200 if result.get("ok") else 400)
        elif path == "/api/voice/browser-ready":
            echo_cancelled = body.get("echo_cancellation") is True
            noise_suppression = body.get("noise_suppression") is True
            auto_gain_control = body.get("auto_gain_control") is True
            audio_runtime.publish(
                device=body.get("device") or "Browser microphone",
                echo_cancelled=echo_cancelled,
                browser_audio=True,
                interruption={
                    "web_ui": True,
                    "keyboard": False,
                    "voice_barge_in": echo_cancelled,
                    "noise_suppression": noise_suppression,
                    "auto_gain_control": auto_gain_control,
                },
                message="Browser voice is ready" if echo_cancelled else "Browser voice ready; echo cancellation was not confirmed",
            )
            self._send_json({"ok": True, "voice_mode": system_power.status()["voice_mode"]})
        elif path == "/api/voice/browser-turn":
            status = system_power.status()
            if not status["powered_on"]:
                self._send_json({"error": "Assistant Core is powered off"}, status=409)
                return
            mode = status["voice_mode"]
            if mode == "off":
                self._send_json({"error": "Browser microphone is off"}, status=409)
                return
            encoded_audio = body.get("audio", "")
            if not isinstance(encoded_audio, str) or not encoded_audio:
                self._send_json({"error": "Audio is required"}, status=400)
                return
            cfg = load_config()
            assistant_name = memory.load_assistant().get("name", "Nova")
            wake_phrases = list(dict.fromkeys(cfg.trigger_phrases + ["hello", "hey", "hi", "assistant", assistant_name]))
            try:
                result = browser_voice.process_turn(
                    encoded_audio,
                    mode=mode,
                    wake_phrases=wake_phrases,
                    assistant_name=assistant_name,
                    user_name=cfg.user_name,
                )
            except (RuntimeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            if result.get("wake") and mode == "wake":
                system_power.set_voice_mode("live", wait=False)
            if result.get("end_conversation"):
                system_power.set_voice_mode("wake", wait=False)
            memory.log_event("voice", f"Browser heard: {result.get('heard', '')}")
            self._send_json(result)
        elif path == "/api/android/call":
            from src.android_bridge import android_bridge
            phone = body.get("phone_number") or body.get("contact", "")
            res = android_bridge.initiate_phone_call(phone)
            self._send_json(res, status=200 if res.get("ok") else 400)
        elif path == "/api/routines/trigger":
            from src.routines import routine_engine
            routine = body.get("routine", "")
            reply = routine_engine.execute_routine(routine)
            self._send_json({"ok": True, "reply": reply})
        elif path == "/api/supervisor/sleep":
            from src.supervisor import supervisor
            duration = float(body.get("duration_seconds", 1800))
            reply = supervisor.schedule_sleep_and_return(duration)
            self._send_json({"ok": True, "reply": reply, "duration_seconds": duration})
        elif path == "/api/actions/undo":
            from src.action_guards import action_guards
            res = action_guards.pop_and_undo()
            self._send_json(res, status=200 if res.get("ok") else 400)
        elif path == "/api/reminders/create":
            raw_text = body.get("text") or body.get("task", "")
            if not raw_text.lower().startswith("remind"):
                raw_text = f"remind me {raw_text}"
            res = tools.parse_and_set_reminder(raw_text)
            if res:
                self._send_json({"ok": True, "reply": res, "reminders": tools.get_active_reminders()})
            else:
                self._send_json({"ok": False, "error": "Could not parse reminder schedule. Try 'remind me in 10 minutes to call mom' or 'remind me tomorrow at 9am to check email'."}, status=400)
        elif path == "/api/reminders/cancel":
            if body.get("all"):
                cnt = tools.cancel_all_reminders()
                self._send_json({"ok": True, "cancelled": cnt, "reminders": []})
            else:
                rem_id = body.get("id", "")
                if rem_id:
                    ok = tools.cancel_reminder(rem_id)
                    self._send_json({"ok": ok, "id": rem_id, "reminders": tools.get_active_reminders()})
                else:
                    self._send_json({"error": "Missing reminder id"}, status=400)
        elif path == "/api/theme":
            theme = body.get("theme", "midnight")
            reply = tools.set_ui_theme(theme)
            self._send_json({"ok": True, "reply": reply, "theme": theme})
        elif path == "/api/location":
            location = body.get("location") or body.get("city", "")
            country = body.get("country", "")
            timezone = body.get("timezone", "")
            coords = body.get("coordinates") or {"lat": body.get("latitude"), "lon": body.get("longitude")}
            weather = body.get("weather") or {}
            full_loc = location
            if country and country not in full_loc:
                full_loc = f"{full_loc}, {country}".strip(", ")
            memory.update_profile_location(
                location=full_loc,
                timezone=timezone,
                coordinates=coords,
                weather=weather
            )
            self._send_json({"ok": True, "location": full_loc})
        elif path == "/api/system/standby":
            action = body.get("action", "enter")
            asst_name = memory.load_assistant().get("name", "Nova")
            if action == "enter":
                print(f"💤 [Standby]: System entered ambient standby mode. Waiting for wake word '{asst_name}'.")
                system_power.set_voice_mode("wake", wait=False)
                self._send_json({"ok": True, "standby": True})
            else:
                print(f"⚡ [Standby]: System awakened from standby mode. Ready for interaction.")
                self._send_json({"ok": True, "standby": False})
        elif path == "/api/ui/control":
            results = []
            if "theme" in body:
                results.append(tools.set_ui_theme(body["theme"]))
            if "visual_engine" in body:
                results.append(tools.set_visual_engine(body["visual_engine"]))
            if "active_tab" in body or "tab" in body:
                t_id = body.get("active_tab") or body.get("tab")
                state = memory.load_state()
                state.setdefault("ui", {})["active_tab"] = t_id
                state["ui"]["tab_updated_at"] = time.time()
                memory.save_state(state)
                results.append(f"Active tab set to {t_id}")
            if "kiosk_mode" in body or "kiosk" in body:
                k_val = body.get("kiosk_mode") if "kiosk_mode" in body else body.get("kiosk")
                results.append(tools.set_kiosk_mode(bool(k_val)))
            self._send_json({"ok": True, "messages": results, "state": memory.load_state().get("ui", {})})
        elif path == "/api/chat":
            user_text = body.get("message", "").strip()
            if not user_text:
                self._send_json({"error": "Empty message"}, status=400)
                return
            asst_name = memory.load_assistant().get("name", "Nova")
            print(f"\n💬 [Web User]: \"{user_text}\"")
            memory.update_assistant_runtime(runtime_state="THINKING", last_heard=user_text)
            reply = agent.process_message(user_text)
            print(f"🤖 [{asst_name}]: \"{reply}\"")
            memory.update_assistant_runtime(runtime_state="SPEAKING", last_heard=user_text, last_reply=reply)
            memory.log_event("agent", f"User: {user_text} -> Nova: {reply}")
            self._send_json({"reply": reply, "history": agent.persistent_history})

        elif path == "/api/assistant-state":
            st = body.get("state", "IDLE")
            last_heard = body.get("last_heard")
            last_reply = body.get("last_reply")
            memory.update_assistant_runtime(st, last_heard=last_heard, last_reply=last_reply)
        elif path == "/api/models/download":
            models_to_download = body.get("models", ["llm_3b", "stt", "tts"])
            ok, msg = downloader.start_download(models_to_download)
            if ok:
                self._send_json({"ok": True, "message": msg})
            else:
                self._send_json({"error": msg}, status=400)

        elif path == "/api/setup/save":
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}

            user_name = body.get("user_name", "").strip()
            if user_name:
                cfg["user_name"] = user_name
                tools.update_preferred_name(user_name)

            assistant_name = body.get("assistant_name", "").strip()
            if assistant_name:
                cfg["assistant_name"] = assistant_name
                memory.update_assistant(name=assistant_name)

            greeting_text = body.get("greeting_text", "").strip()
            if greeting_text:
                cfg["greeting_text"] = greeting_text

            if "trigger_phrases" in body and isinstance(body["trigger_phrases"], list):
                cfg["trigger_phrases"] = [p.strip().lower() for p in body["trigger_phrases"] if p.strip()]

            if "phone_ip" in body:
                cfg["phone_ip"] = body["phone_ip"].strip()

            if "microphone_device" in body:
                cfg["microphone_device"] = body["microphone_device"]

            if "voice_name" in body:
                cfg["voice_name"] = str(body["voice_name"]).strip()

            if "ready_chime" in body:
                cfg["ready_chime"] = bool(body["ready_chime"])

            if "ai_mode" in body:
                cfg["ai_mode"] = body["ai_mode"] # "local" or "cloud"

            if "cloud_provider" in body:
                cfg["cloud_provider"] = body["cloud_provider"]

            if "cloud_api_key" in body:
                cfg["cloud_api_key"] = body["cloud_api_key"].strip()

            if "llm_provider" in body:
                cfg["llm_provider"] = body["llm_provider"]
            elif "cloud_provider" in body and body.get("ai_mode") == "cloud":
                cfg["llm_provider"] = body["cloud_provider"]

            if "llm_model" in body:
                cfg["llm_model"] = body["llm_model"]

            if "llm_api_key" in body:
                cfg["llm_api_key"] = body["llm_api_key"].strip() if body["llm_api_key"] else None

            if "llm_base_url" in body:
                cfg["llm_base_url"] = body["llm_base_url"].strip() if body["llm_base_url"] else None

            # Save user bio/background notes as learned facts in memory
            bio_notes = body.get("bio_notes", "").strip()
            if bio_notes:
                # Add overall profile note or individual facts
                lines = [line.strip().lstrip("*-• ") for line in bio_notes.split("\n") if line.strip()]
                for line in lines:
                    if len(line) > 3:
                        tools.remember_fact(f"User context: {line}")

            cfg["setup_completed"] = True

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)

            brain.reload(load_config())
            self._send_json({"ok": True, "message": "Setup saved successfully", "config": cfg})

        elif path == "/api/setup/launch":
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                cfg["setup_completed"] = True
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
            except Exception:
                pass
            self._send_json({"ok": True, "message": "Ready to launch assistant!"})

        elif path == "/api/config":
            # Update config fields
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}

            if "user_name" in body:
                tools.update_preferred_name(body["user_name"])
                cfg["user_name"] = body["user_name"]
            if "assistant_name" in body and body["assistant_name"]:
                cfg["assistant_name"] = body["assistant_name"]
                memory.update_assistant(name=body["assistant_name"])
            if "greeting_text" in body:
                cfg["greeting_text"] = body["greeting_text"]
            if "phone_ip" in body:
                cfg["phone_ip"] = str(body["phone_ip"]).strip()
            if "user_bio" in body and body["user_bio"]:
                bio_text = str(body["user_bio"]).strip()
                lines = [line.strip().lstrip("*-• ") for line in bio_text.split("\n") if line.strip()]
                for line in lines:
                    if len(line) > 3:
                        tools.remember_fact(f"User context: {line}")
            if "mac_addresses" in body and isinstance(body["mac_addresses"], list):
                cfg["mac_addresses"] = body["mac_addresses"]
            if "llm_provider" in body:
                cfg["llm_provider"] = body["llm_provider"]
                cfg["ai_mode"] = "cloud" if body["llm_provider"] != "local" else "local"
            if "llm_model" in body:
                cfg["llm_model"] = body["llm_model"]
            if "llm_api_key" in body:
                cfg["llm_api_key"] = body["llm_api_key"].strip() if body["llm_api_key"] else None
            if "llm_base_url" in body:
                cfg["llm_base_url"] = body["llm_base_url"].strip() if body["llm_base_url"] else None
            if "voice_name" in body:
                cfg["voice_name"] = str(body["voice_name"]).strip()
            for field in ("ready_chime", "echo_cancellation"):
                if field in body:
                    if not isinstance(body[field], bool):
                        self._send_json({"error": f"{field} must be a boolean"}, status=400)
                        return
                    cfg[field] = body[field]
            for field, upper in (("conversation_timeout_seconds", 300), ("conversation_phrase_limit_seconds", 60)):
                if field in body:
                    if type(body[field]) is not int or not 5 <= body[field] <= upper:
                        self._send_json({"error": f"{field} must be between 5 and {upper}"}, status=400)
                        return
                    cfg[field] = body[field]
            if "microphone_device" in body:
                device = body["microphone_device"]
                if device is not None and not isinstance(device, (str, int)):
                    self._send_json({"error": "Invalid microphone device"}, status=400)
                    return
                cfg["microphone_device"] = device

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)

            brain.reload(load_config())
            self._send_json({"ok": True, "config": cfg})

        elif path == "/api/memory":
            action = body.get("action")
            if action == "add":
                fact = body.get("fact", "").strip()
                if fact:
                    res = tools.remember_fact(fact)
                    self._send_json({"ok": True, "result": res})
                else:
                    self._send_json({"error": "Fact cannot be empty"}, status=400)

            elif action == "delete":
                idx = body.get("index")
                try:
                    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                        mem = json.load(f)
                    facts = mem.get("learned_facts", [])
                    if 0 <= idx < len(facts):
                        removed = facts.pop(idx)
                        mem["learned_facts"] = facts
                        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
                            json.dump(mem, f, indent=2)
                        self._send_json({"ok": True, "removed": removed})
                    else:
                        self._send_json({"error": "Index out of range"}, status=400)
                except Exception as e:
                    self._send_json({"error": str(e)}, status=500)
            else:
                self._send_json({"error": "Unknown action"}, status=400)

        elif path == "/api/timer":
            action = body.get("action")
            if action == "cancel":
                timer_id = body.get("id")
                ok = tools.cancel_timer(timer_id)
                self._send_json({"ok": ok, "message": "Timer canceled" if ok else "Timer not found"})
                return
            elif action == "cancel_all":
                count = tools.cancel_all_timers()
                self._send_json({"ok": True, "message": f"Canceled {count} active timers"})
                return

            seconds = body.get("seconds")
            clock_time = body.get("clock_time")
            label = body.get("label", "alarm")

            if seconds:
                res = tools.set_timer(float(seconds), label=label)
                self._send_json({"ok": True, "message": res})
            elif clock_time:
                res = tools.set_clock_alarm(clock_time, label=label)
                self._send_json({"ok": True, "message": res})
            else:
                self._send_json({"error": "Provide seconds, clock_time, or action='cancel'"}, status=400)

        elif path == "/api/knowledge":
            if not isinstance(body, dict):
                self._send_json({"error": "Knowledge payload must be a JSON object"}, status=400)
                return
            memory.save_app_knowledge(body)
            brain.reset_history()
            self._send_json({"ok": True, "message": "App knowledge updated successfully", "knowledge": memory.load_app_knowledge()})

        elif path == "/api/system/request_mic_permission":
            import platform, subprocess
            os_name = platform.system()
            if os_name == "Windows":
                try:
                    subprocess.Popen(["start", "ms-settings:privacy-microphone"], shell=True)
                except Exception:
                    pass
                self._send_json({
                    "ok": True,
                    "granted": True,
                    "status": "WINDOWS",
                    "message": "Opened Windows Microphone Privacy Settings."
                })
                return
            elif os_name != "Darwin":
                self._send_json({
                    "ok": True,
                    "granted": True,
                    "status": "LINUX",
                    "message": "On Linux, check your PulseAudio/PipeWire mixer permissions."
                })
                return

            swift_code = '''
import AVFoundation

let status = AVCaptureDevice.authorizationStatus(for: .audio)
if status == .notDetermined {
    let sema = DispatchSemaphore(value: 0)
    AVCaptureDevice.requestAccess(for: .audio) { granted in
        print(granted ? "GRANTED" : "DENIED")
        sema.signal()
    }
    _ = sema.wait(timeout: .now() + 10.0)
} else if status == .authorized {
    print("GRANTED")
} else {
    print("DENIED")
}
'''
            try:
                res = subprocess.run(["swift", "-e", swift_code], capture_output=True, text=True, timeout=12)
                out = res.stdout.strip()
                granted = "GRANTED" in out
                if not granted:
                    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"])
                self._send_json({
                    "ok": True,
                    "granted": granted,
                    "status": out or ("GRANTED" if granted else "DENIED"),
                    "message": "Microphone permission is granted for Terminal!" if granted else "Microphone access blocked. Opened macOS System Settings."
                })
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)

        else:
            self.send_error(404, "Endpoint Not Found")

    def log_message(self, format, *args):
        # Quiet web logger to prevent cluttering assistant terminal
        pass


def run_web_server(host="0.0.0.0", port=5050, background=False, open_browser=False):
    actual_port = port
    server = None
    for offset in range(25):
        test_port = port + offset
        try:
            server = ThreadingHTTPServer((host, test_port), AssistantRequestHandler)
            actual_port = test_port
            break
        except OSError as e:
            # 48 on macOS, 98 on Linux, 10048 on Windows
            if e.errno in (48, 98, 10048) or "address already in use" in str(e).lower() or "already in use" in str(e).lower():
                continue
            if offset < 24:
                continue
            raise

    if server is None:
        print(f"❌ [Web UI] Could not bind to port {port} or next 25 ports.")
        return None

    local_url = f"http://localhost:{actual_port}"
    print(f"\n🌐 [Web UI] Local Configuration Dashboard running at:")
    print(f"   👉 Local:   {local_url}")
    print(f"   👉 Network: http://{host}:{actual_port}\n")

    if background:
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

    if open_browser:
        from src.setup_wizard import is_first_time_setup
        target_url = f"{local_url}/setup" if is_first_time_setup() else local_url
        browser_timer = threading.Timer(0.5, webbrowser.open, args=(target_url,))
        browser_timer.daemon = True
        browser_timer.start()

    if background:
        return server

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Web UI] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    run_web_server(port=5050, background=False)
