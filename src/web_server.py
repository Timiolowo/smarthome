import json
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from src.agent import agent
from src.memory import memory
from src.tools import tools, play_alarm_sound

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
    assistant_runtime = state.get("assistant_runtime", {
        "state": "IDLE",
        "last_heard": "",
        "last_reply": "",
        "updated_at": datetime.now().isoformat(),
    })

    return {
        "config": cfg,
        "assistant": assistant_info,
        "memory": mem,
        "state": state,
        "models": models_info,
        "active_timers": len(active_timers),
        "active_timers_list": active_timers,
        "assistant_runtime": assistant_runtime,
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
            index_file = os.path.join(WEB_DIR, "index.html")
            self._send_file(index_file, "text/html")
        elif path == "/api/status":
            self._send_json(get_system_status())
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
        else:
            # Check for static files under WEB_DIR (css, js, icons, etc.)
            clean_rel = os.path.normpath(path.lstrip("/"))
            target_path = os.path.abspath(os.path.join(WEB_DIR, clean_rel))
            if os.path.isfile(target_path) and os.path.commonpath([WEB_DIR, target_path]) == WEB_DIR:
                ext = os.path.splitext(target_path)[1].lower()
                mimes = {
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
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        if path == "/api/chat":
            user_text = body.get("message", "").strip()
            if not user_text:
                self._send_json({"error": "Empty message"}, status=400)
                return
            memory.update_assistant_runtime(runtime_state="THINKING", last_heard=user_text)
            reply = agent.process_message(user_text)
            memory.update_assistant_runtime(runtime_state="SPEAKING", last_heard=user_text, last_reply=reply)
            memory.log_event("agent", f"User: {user_text} -> Nova: {reply}")
            self._send_json({"reply": reply, "history": agent.persistent_history})

        elif path == "/api/assistant-state":
            st = body.get("state", "IDLE")
            last_heard = body.get("last_heard")
            last_reply = body.get("last_reply")
            memory.update_assistant_runtime(st, last_heard=last_heard, last_reply=last_reply)
            self._send_json({"ok": True})

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
            if "assistant_name" in body:
                cfg["assistant_name"] = body["assistant_name"]
            if "greeting_text" in body:
                cfg["greeting_text"] = body["greeting_text"]
            if "mac_addresses" in body and isinstance(body["mac_addresses"], list):
                cfg["mac_addresses"] = body["mac_addresses"]

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)

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

        else:
            self.send_error(404, "Endpoint Not Found")

    def log_message(self, format, *args):
        # Quiet web logger to prevent cluttering assistant terminal
        pass


def run_web_server(host="0.0.0.0", port=5050, background=False):
    actual_port = port
    server = None
    for offset in range(10):
        test_port = port + offset
        try:
            server = ThreadingHTTPServer((host, test_port), AssistantRequestHandler)
            actual_port = test_port
            break
        except OSError as e:
            if e.errno == 48: # Address already in use
                continue
            raise

    if server is None:
        print(f"❌ [Web UI] Could not bind to port {port} or next 10 ports.")
        return None

    print(f"\n🌐 [Web UI] Local Configuration Dashboard running at:")
    print(f"   👉 Local:   http://localhost:{actual_port}")
    print(f"   👉 Network: http://{host}:{actual_port}\n")

    if background:
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return server
    else:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[Web UI] Shutting down...")
            server.shutdown()


if __name__ == "__main__":
    run_web_server(port=5050, background=False)
