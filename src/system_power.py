"""
System Power Controller for Home AI Assistant.
Controls Assistant Core lifecycle (power on, power off, wake-word activation).
"""

import threading
from typing import Callable, Optional
from src import audio_runtime
from src.interruption import response_interruption
from src.memory import memory


class SystemPowerManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._mode_changed = threading.Condition(self._lock)
        self.powered_on = True
        self.stop_event = threading.Event()
        self.voice_change_event = threading.Event()
        self._voice_mode = "wake"
        self._applied_voice_mode = "starting"
        self._voice_loop_active = False
        self._audio_owner = "browser"
        self.worker_thread: Optional[threading.Thread] = None
        self._loop_starter: Optional[Callable] = None
        self.simulate_presence = True

    def register_loop_starter(self, starter_fn: Callable):
        """Registers the callable that starts the assistant voice loop."""
        self._loop_starter = starter_fn

    def prepare_for_direct_run(self, simulate_presence: bool = False) -> None:
        """Resets lifecycle signals before the initial foreground voice loop starts."""
        with self._lock:
            self.powered_on = True
            self._voice_mode = "wake"
            self._applied_voice_mode = "starting"
            self._voice_loop_active = False
            self.simulate_presence = simulate_presence
            self.stop_event.clear()
            self.voice_change_event.clear()

    def is_powered_on(self) -> bool:
        with self._lock:
            return self.powered_on

    def status(self) -> dict:
        with self._lock:
            return {
                "powered_on": self.powered_on,
                "state": "ONLINE" if self.powered_on else "OFFLINE",
                "worker_alive": self._voice_loop_active,
                "voice_backend_active": self._voice_loop_active,
                "requested_voice_mode": self._voice_mode,
                "voice_mode": self._applied_voice_mode,
                "audio_owner": self._audio_owner,
            }

    def voice_mode(self) -> str:
        with self._lock:
            return self._voice_mode

    def mark_voice_loop_started(self) -> None:
        with self._mode_changed:
            self._voice_loop_active = True
            self._applied_voice_mode = "starting"
            self._mode_changed.notify_all()

    def acknowledge_voice_mode(self, mode: str) -> None:
        with self._mode_changed:
            self._applied_voice_mode = mode
            self._mode_changed.notify_all()

    def mark_voice_loop_stopped(self) -> None:
        with self._mode_changed:
            self._voice_loop_active = False
            self._applied_voice_mode = "off" if not self.powered_on else "stopped"
            self._mode_changed.notify_all()

    def set_voice_mode(self, mode: str, wait: bool = True, timeout: float = 10.0) -> dict:
        """Switches the terminal voice loop between wake, live, and microphone-off modes."""
        if mode not in {"wake", "live", "off"}:
            return {"ok": False, "error": "voice mode must be 'wake', 'live', or 'off'"}

        with self._mode_changed:
            if not self.powered_on:
                return {"ok": False, "error": "Assistant Core is powered off"}
            if not self._voice_loop_active:
                return {"ok": False, "error": "Terminal voice backend is not running"}
            self._voice_mode = mode
            self.voice_change_event.set()

        response_interruption.interrupt()

        labels = {
            "wake": ('WAITING_FOR_NOVA', 'Waiting for “Nova”'),
            "live": ('LIVE_LISTENING', 'Live listening'),
            "off": ('MICROPHONE_OFF', 'Microphone off'),
        }
        runtime_state, message = labels[mode]
        if mode in {"wake", "off"}:
            try:
                from src.voice_output import stop
                stop()
            except Exception:
                pass
        if wait:
            with self._mode_changed:
                applied = self._mode_changed.wait_for(
                    lambda: self._applied_voice_mode == mode or not self._voice_loop_active,
                    timeout=timeout,
                )
                if not applied or self._applied_voice_mode != mode:
                    return {
                        "ok": False,
                        "error": f"Terminal voice backend did not apply '{mode}' mode",
                        **self.status_unlocked(),
                    }
        audio_runtime.publish(state=runtime_state, message=message, voice_mode=mode)
        memory.update_assistant_runtime(runtime_state=runtime_state)
        return {"ok": True, **self.status(), "message": message}

    def status_unlocked(self) -> dict:
        return {
            "powered_on": self.powered_on,
            "state": "ONLINE" if self.powered_on else "OFFLINE",
            "worker_alive": self._voice_loop_active,
            "voice_backend_active": self._voice_loop_active,
            "requested_voice_mode": self._voice_mode,
            "voice_mode": self._applied_voice_mode,
            "audio_owner": self._audio_owner,
        }

    def power_off(self) -> dict:
        with self._lock:
            if not self.powered_on:
                return {"ok": True, "powered_on": False, "state": "OFFLINE", "message": "Already powered off"}

            self.powered_on = False
            self._voice_mode = "off"
            self.stop_event.set()
            self.voice_change_event.set()
            response_interruption.interrupt()

            # Silence any active speaker
            try:
                from src.voice_output import stop
                stop()
            except Exception:
                pass

            audio_runtime.publish(state='POWER_OFF', message='Assistant Core powered off')
            memory.update_assistant_runtime(runtime_state='OFFLINE')
            print("\n🛑 [System Power]: Assistant Core Powered OFF via Voice Hub / Wake Command.")
            return {"ok": True, "powered_on": False, "state": "OFFLINE", "message": "Assistant Core powered off"}

    def power_on(self, simulate_presence: Optional[bool] = None) -> dict:
        with self._lock:
            if simulate_presence is not None:
                self.simulate_presence = simulate_presence

            if self.powered_on and self.worker_thread and self.worker_thread.is_alive():
                return {"ok": True, "powered_on": True, "state": "ONLINE", "message": "Already powered on"}

            self.powered_on = True
            self._voice_mode = "wake"
            self._applied_voice_mode = "starting"
            self.stop_event.clear()
            self.voice_change_event.set()

            audio_runtime.publish(state='STARTING', message='Powering on Assistant Core...')
            memory.update_assistant_runtime(runtime_state='STARTING')
            print("\n⚡ [System Power]: Assistant Core Powered ON! Initializing voice loop...")

            if self._loop_starter:
                self.worker_thread = threading.Thread(
                    target=self._run_loop_wrapper,
                    daemon=True,
                    name="AssistantVoiceCoreWorker"
                )
                self.worker_thread.start()

            return {"ok": True, "powered_on": True, "state": "ONLINE", "message": "Assistant Core powered on"}

    def _run_loop_wrapper(self):
        try:
            if self._loop_starter:
                self._loop_starter(self.stop_event, self.simulate_presence)
        except Exception as exc:
            print(f"[System Power] Assistant loop exited with error: {exc}")
        finally:
            with self._lock:
                if not self.powered_on:
                    audio_runtime.publish(state='OFFLINE', message='Assistant Core is powered off')

    def toggle(self) -> dict:
        if self.is_powered_on():
            return self.power_off()
        else:
            return self.power_on()


system_power = SystemPowerManager()
