"""
Live Terminal Output Interceptor & Logger for Smart Home Assistant.
Captures standard output and console prints in real time to stream to the Web UI Live Terminal modal.
"""

import sys
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional


class TerminalLogManager:
    def __init__(self, max_lines: int = 1000):
        self.max_lines = max_lines
        self.lines: deque = deque(maxlen=max_lines)
        self._lock = threading.Lock()
        self._counter = 0
        self._installed = False
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

    def append(self, text: str, level: str = "info") -> None:
        if not text or not text.strip():
            return
        clean_text = text.rstrip("\r\n")
        
        # Categorize log entry
        log_type = "info"
        if "🎤" in clean_text or "[Heard]" in clean_text:
            log_type = "heard"
        elif "🤖" in clean_text:
            log_type = "assistant"
        elif "🛑" in clean_text or "Interrupted" in clean_text:
            log_type = "power_off"
        elif "⚡" in clean_text:
            log_type = "power_on"
        elif "💤" in clean_text or "[Standby]" in clean_text:
            log_type = "standby"
        elif "👉" in clean_text or "[Command]" in clean_text:
            log_type = "command"
        elif "❌" in clean_text or "Error" in clean_text or level == "error":
            log_type = "error"
        elif any(tag in clean_text for tag in ("[BrowserVoice]", "[LLMProvider]", "[System Power]", "[Memory]", "[Standby]", "🌐", "🏡")):
            log_type = "system"

        with self._lock:
            self._counter += 1
            entry = {
                "id": self._counter,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "text": clean_text,
                "type": log_type,
                "level": level,
            }
            self.lines.append(entry)

    def get_logs(self, limit: int = 200, since_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self.lines)
            if since_id is not None:
                items = [item for item in items if item["id"] > since_id]
            return items[-limit:]

    def clear(self) -> None:
        with self._lock:
            self.lines.clear()

    def install(self) -> None:
        if self._installed:
            return
        self._installed = True

        class StdoutTee:
            def __init__(self, orig_stream, manager, is_stderr=False):
                self._orig = orig_stream
                self._manager = manager
                self._is_stderr = is_stderr
                self._buffer = ""
                self._tee_lock = threading.Lock()

            def write(self, data):
                try:
                    self._orig.write(data)
                    self._orig.flush()
                except Exception:
                    pass

                if not data:
                    return

                with self._tee_lock:
                    self._buffer += data
                    while "\n" in self._buffer:
                        line, self._buffer = self._buffer.split("\n", 1)
                        clean = line.rstrip("\r")
                        if clean:
                            self._manager.append(clean, level="error" if self._is_stderr else "info")

            def flush(self):
                try:
                    self._orig.flush()
                except Exception:
                    pass

            def fileno(self):
                return self._orig.fileno()

            def isatty(self):
                return self._orig.isatty()

            def __getattr__(self, name):
                return getattr(self._orig, name)

        sys.stdout = StdoutTee(self._orig_stdout, self, is_stderr=False)
        sys.stderr = StdoutTee(self._orig_stderr, self, is_stderr=True)


terminal_logger = TerminalLogManager()
terminal_logger.install()
