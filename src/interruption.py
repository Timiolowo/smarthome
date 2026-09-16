"""Thread-safe cancellation for the currently active assistant response."""

import threading


class ResponseInterruption:
    def __init__(self):
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._active = False

    def begin_response(self) -> threading.Event:
        """Give a new response its own cancellation signal."""
        with self._lock:
            self._event = threading.Event()
            self._active = True
            return self._event

    def interrupt(self) -> bool:
        """Cancel the active response without changing microphone mode."""
        with self._lock:
            was_active = self._active
            self._event.set()
            return was_active

    def finish_response(self, event: threading.Event) -> None:
        with self._lock:
            if self._event is event:
                self._active = False

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def is_interrupted(self) -> bool:
        with self._lock:
            return self._event.is_set()


response_interruption = ResponseInterruption()
