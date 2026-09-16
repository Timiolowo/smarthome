"""
Autonomous Supervisor & Scheduler for Smart Home Assistant.
Manages timed sleep/return cycles, downtime tracking, return greetings,
arrival briefings, smart-home routines, and system watchdogs.
"""

import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.memory import memory
from src.system_power import system_power


class Supervisor:
    def __init__(self):
        self.sleep_timer: Optional[threading.Timer] = None
        self.sleep_record: Optional[Dict[str, Any]] = None
        self.notification_queue: List[Dict[str, Any]] = []
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_stop = threading.Event()
        self._lock = threading.Lock()
        self.restore_active_sleep_if_any()

    def restore_active_sleep_if_any(self) -> None:
        """Restores pending scheduled sleep if target wake timestamp is in the future."""
        try:
            state = memory.load_state()
            active_sleep = state.get("downtime", {}).get("active_sleep")
            if active_sleep and active_sleep.get("target_wake_timestamp"):
                target_ts = float(active_sleep["target_wake_timestamp"])
                now = time.time()
                remaining = target_ts - now
                if remaining > 0:
                    system_power.power_off()
                    with self._lock:
                        self.sleep_record = {
                            "sleep_start": now - (active_sleep.get("target_duration_seconds", remaining) - remaining),
                            "target_wake": target_ts,
                            "duration_seconds": active_sleep.get("target_duration_seconds", remaining),
                            "duration_desc": active_sleep.get("duration_desc", f"{int(remaining)}s"),
                            "label": "sleep",
                        }
                    def _wake_cb():
                        self._handle_scheduled_wake()
                    t = threading.Timer(remaining, _wake_cb)
                    t.daemon = True
                    self.sleep_timer = t
                    t.start()
                else:
                    state["downtime"]["active_sleep"] = None
                    memory.save_state(state)
        except Exception:
            pass

    def schedule_sleep_and_return(self, duration_seconds: float, label: str = "sleep") -> str:
        """
        Puts Nova into sleep / downtime mode for duration_seconds and automatically wakes up.
        Example: "turn yourself off and return in 30 minutes".
        """
        if duration_seconds <= 0:
            return "Sleep duration must be greater than zero."

        # Cancel any existing sleep timer
        self.cancel_sleep()

        now = time.time()
        wake_timestamp = now + duration_seconds
        mins = round(duration_seconds / 60, 1)
        duration_desc = f"{int(duration_seconds)} seconds" if duration_seconds < 60 else (
            f"{int(mins)} minute" if mins == 1 else f"{mins} minutes"
        )

        with self._lock:
            self.sleep_record = {
                "sleep_start": now,
                "target_wake": wake_timestamp,
                "duration_seconds": duration_seconds,
                "duration_desc": duration_desc,
                "label": label,
            }

        # Update persistent state
        state = memory.load_state()
        state.setdefault("downtime", {})["active_sleep"] = {
            "start": datetime.now().isoformat(),
            "target_duration_seconds": duration_seconds,
            "target_wake": datetime.fromtimestamp(wake_timestamp).isoformat(),
            "target_wake_timestamp": wake_timestamp,
            "duration_desc": duration_desc,
        }
        memory.save_state(state)
        memory.log_event("supervisor", f"Entered scheduled sleep for {duration_desc}")

        def _wake_callback():
            self._handle_scheduled_wake()

        t = threading.Timer(duration_seconds, _wake_callback)
        t.daemon = True
        self.sleep_timer = t
        t.start()

        # Silence and power off voice loop
        system_power.power_off()

        return f"Shutting down and coming back online in {duration_desc}."

    def _handle_scheduled_wake(self) -> None:
        """Called automatically when the sleep duration expires."""
        with self._lock:
            record = self.sleep_record
            self.sleep_record = None
            self.sleep_timer = None

        now = time.time()
        downtime_secs = (now - record["sleep_start"]) if record else 0.0

        # Power on Assistant Core
        system_power.power_on()

        # Generate return greeting
        greeting = self.generate_return_greeting(downtime_secs)
        print(f"\n🌅 [SUPERVISOR AWAKEN]: {greeting}")

        # Update state and memory log
        state = memory.load_state()
        state.setdefault("downtime", {})["last_downtime_seconds"] = round(downtime_secs, 1)
        state["downtime"]["active_sleep"] = None
        memory.save_state(state)
        memory.log_event("supervisor", f"Awakened after {round(downtime_secs / 60, 1)}m downtime. {greeting}")

        # Dispatch proactive notification and speak return greeting
        self.emit_notification("wake", greeting)
        try:
            from src.voice_output import speak
            speak(greeting, interruptible=True)
        except Exception:
            pass

    def generate_return_greeting(self, downtime_seconds: float) -> str:
        """Constructs a warm, natural return greeting after downtime."""
        mem_data = memory.load_memory()
        user_name = mem_data.get("profile", {}).get("preferred_name", "Timilehin")
        asst_name = memory.load_assistant().get("name", "Nova")

        mins = round(downtime_seconds / 60, 1)
        if mins < 1:
            time_str = f"{int(downtime_seconds)} seconds"
        elif mins < 60:
            time_str = f"{int(mins)} minute" if mins == 1 else f"{int(mins)} minutes"
        else:
            hrs = round(mins / 60, 1)
            time_str = f"{hrs} hour" if hrs == 1 else f"{hrs} hours"

        greetings = [
            f"I'm back online, {user_name}. That was {time_str} of downtime. Ready when you are!",
            f"Hello {user_name}, {asst_name} is back and active after {time_str}. How can I assist?",
            f"System restored. I've completed my {time_str} scheduled rest. What are we working on, {user_name}?",
        ]
        import random
        return random.choice(greetings)

    def cancel_sleep(self) -> bool:
        """Cancels any scheduled sleep/return timer."""
        with self._lock:
            canceled = False
            if self.sleep_timer:
                try:
                    self.sleep_timer.cancel()
                except Exception:
                    pass
                self.sleep_timer = None
                canceled = True
            self.sleep_record = None
            try:
                state = memory.load_state()
                if state.get("downtime", {}).get("active_sleep"):
                    state["downtime"]["active_sleep"] = None
                    memory.save_state(state)
            except Exception:
                pass
            return canceled

    def emit_notification(self, category: str, message: str, level: str = "info") -> None:
        """Queues a proactive notification for frontend HUD and logs."""
        entry = {
            "id": f"notif_{int(time.time() * 1000)}",
            "category": category,
            "message": message,
            "level": level,
            "timestamp": datetime.now().isoformat(),
        }
        with self._lock:
            self.notification_queue.append(entry)
            if len(self.notification_queue) > 50:
                self.notification_queue.pop(0)

    def get_notifications(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.notification_queue)

    def get_arrival_briefing(self) -> str:
        """Constructs a proactive arrival briefing when user returns home."""
        mem_data = memory.load_memory()
        user_name = mem_data.get("profile", {}).get("preferred_name", "Timilehin")
        from src.tools import tools
        from src.platform_adapter import platform_adapter

        reminders = tools.get_active_reminders()
        rem_count = len(reminders)
        wifi = platform_adapter.get_wifi_status()
        batt = platform_adapter.get_battery_status()

        parts = [f"Welcome home, {user_name}."]
        if rem_count > 0:
            parts.append(f"You have {rem_count} upcoming reminder{'s' if rem_count > 1 else ''}.")
        else:
            parts.append("No pending reminders.")

        if wifi.get("connected"):
            parts.append(f"Connected to {wifi.get('ssid')}.")
        if batt.get("has_battery") and batt.get("percent") is not None:
            parts.append(f"Battery is at {batt.get('percent')}%.")

        return " ".join(parts)


supervisor = Supervisor()
