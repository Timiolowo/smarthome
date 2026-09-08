import json
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.voice_output import speak

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
LOG_FILE = os.path.join(DATA_DIR, "memory_log.jsonl")


def play_alarm_sound(repeats: int = 2) -> None:
    """Generates and plays a crisp 3-beep alarm chime directly through speakers."""
    try:
        import numpy as np
        import sounddevice as sd

        sample_rate = 22050
        duration = 0.12
        silence = 0.08

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Harmonically rich alarm tone (880 Hz A5 + 1760 Hz A6)
        tone = 0.6 * np.sin(2 * np.pi * 880 * t) + 0.3 * np.sin(2 * np.pi * 1760 * t)
        envelope = np.sin(np.pi * np.linspace(0, 1, len(t)))
        beep = (tone * envelope).astype(np.float32)
        gap = np.zeros(int(sample_rate * silence), dtype=np.float32)
        pause = np.zeros(int(sample_rate * 0.35), dtype=np.float32)

        # 3 quick beeps per cycle
        cycle = np.concatenate([beep, gap, beep, gap, beep, pause])
        full_audio = np.tile(cycle, repeats)

        sd.play(full_audio, samplerate=sample_rate)
        sd.wait()
    except Exception as e:
        print(f"[Alarm] Notice: Audio chime fallback ({e})")


class AgentTools:
    def __init__(self):
        self.active_timers: List[threading.Timer] = []
        self.timer_records: List[Dict[str, Any]] = []

    def update_preferred_name(self, new_name: str) -> str:
        """Updates the user's name across memory.json and config.json."""
        cleaned_name = new_name.strip().capitalize()
        if not cleaned_name:
            return "I couldn't catch the new name."

        # 1. Update data/memory.json
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                mem_data = json.load(f)
            mem_data.setdefault("profile", {})["preferred_name"] = cleaned_name
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(mem_data, f, indent=2)
        except Exception as e:
            print(f"[Tools] Failed to update memory.json: {e}")

        # 2. Update config.json
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            cfg_data["user_name"] = cleaned_name
            cfg_data["greeting_text"] = f"Welcome home, {cleaned_name}. How was your day?"
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg_data, f, indent=2)
        except Exception as e:
            print(f"[Tools] Failed to update config.json: {e}")

        # 3. Log event
        self._log_event("identity", f"User changed preferred name to '{cleaned_name}'")
        return f"Got it. I will address you as {cleaned_name} from now on."

    def remember_fact(self, fact: str, category: str = "personal") -> str:
        """Stores a persistent fact into data/memory.json so it is never forgotten."""
        cleaned_fact = fact.strip()
        if not cleaned_fact:
            return "What would you like me to remember?"

        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                mem_data = json.load(f)

            facts = mem_data.setdefault("learned_facts", [])
            # Avoid duplicate entries
            if cleaned_fact not in facts:
                facts.append(cleaned_fact)

            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(mem_data, f, indent=2)

            self._log_event("memory", f"Learned fact: {cleaned_fact}")
            return f"Noted. I'll remember that {cleaned_fact}."
        except Exception as e:
            print(f"[Tools] Error saving fact: {e}")
            return "I had trouble saving that to memory."

    def set_timer(self, seconds: float, label: str = "alarm") -> str:
        """Sets a non-blocking background timer that rings an alarm sound and announces when finished."""
        if seconds <= 0:
            return "Duration must be greater than zero."

        if seconds < 60:
            display_time = f"{int(seconds)} seconds"
        elif seconds < 3600:
            mins = int(seconds // 60)
            display_time = f"{mins} minute" if mins == 1 else f"{mins} minutes"
        else:
            hrs = round(seconds / 3600, 1)
            display_time = f"{hrs} hours"

        end_timestamp = time.time() + seconds
        record = {
            "id": f"timer_{int(end_timestamp)}_{len(self.timer_records)}",
            "label": label,
            "display_time": display_time,
            "total_seconds": seconds,
            "end_timestamp": end_timestamp,
            "created_at": datetime.now().isoformat(),
        }
        self.timer_records.append(record)

        def _timer_callback():
            print(f"\n⏰ [ALARM TRIGGERED]: {label.capitalize()} for {display_time} is up!")
            try:
                self.timer_records = [r for r in self.timer_records if r.get("id") != record["id"]]
            except Exception:
                pass
            play_alarm_sound(repeats=2)
            time.sleep(0.3)
            alert_msg = f"Your {label} for {display_time} is up."
            speak(alert_msg, interruptible=False)

        t = threading.Timer(seconds, _timer_callback)
        t.daemon = True
        record["timer_obj"] = t
        t.start()
        self.active_timers.append(t)

        self._log_event("timer", f"Set {label} for {display_time}")
        return f"Alarm set for {display_time}."

    def set_clock_alarm(self, target_time_str: str, label: str = "alarm") -> str:
        """Sets an alarm for a specific clock time (e.g. '7:30 am', '8 pm', '14:00')."""
        try:
            now = datetime.now()
            clean_time = target_time_str.strip().upper()
            target_dt = None

            for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M"):
                try:
                    parsed = datetime.strptime(clean_time, fmt)
                    target_dt = now.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
                    break
                except ValueError:
                    continue

            if not target_dt:
                return f"I couldn't understand the time '{target_time_str}'."

            # If the clock time has already passed today, set for tomorrow
            if target_dt <= now:
                import datetime as dt
                target_dt += dt.timedelta(days=1)

            diff_seconds = (target_dt - now).total_seconds()
            display_target = target_dt.strftime("%I:%M %p").lstrip("0")
            end_timestamp = time.time() + diff_seconds

            clock_record = {
                "id": f"clock_{int(end_timestamp)}_{len(self.timer_records)}",
                "label": label,
                "display_time": display_target,
                "total_seconds": diff_seconds,
                "end_timestamp": end_timestamp,
                "created_at": datetime.now().isoformat(),
            }
            self.timer_records.append(clock_record)

            def _clock_callback():
                print(f"\n⏰ [CLOCK ALARM TRIGGERED]: {label.capitalize()} for {display_target}!")
                try:
                    self.timer_records = [r for r in self.timer_records if r.get("id") != clock_record["id"]]
                except Exception:
                    pass
                play_alarm_sound(repeats=2)
                time.sleep(0.3)
                speak(f"It is {display_target}. Your {label} is ringing.", interruptible=False)

            t = threading.Timer(diff_seconds, _clock_callback)
            t.daemon = True
            clock_record["timer_obj"] = t
            t.start()
            self.active_timers.append(t)

            self._log_event("alarm", f"Set clock alarm for {display_target}")
            return f"Alarm set for {display_target}."
        except Exception as e:
            return f"Couldn't set alarm for {target_time_str}."

    def get_active_timers(self) -> List[Dict[str, Any]]:
        """Returns list of active timers with calculated remaining seconds."""
        now_ts = time.time()
        active = []
        valid_records = []
        for r in self.timer_records:
            rem = max(0.0, r["end_timestamp"] - now_ts)
            if rem > 0:
                valid_records.append(r)
                target_dt = datetime.fromtimestamp(r["end_timestamp"])
                active.append({
                    "id": r.get("id"),
                    "label": r.get("label", "Timer"),
                    "display_time": r.get("display_time", ""),
                    "target_display": target_dt.strftime("%I:%M %p"),
                    "total_seconds": r.get("total_seconds", 0),
                    "remaining_seconds": round(rem, 1),
                    "progress_pct": max(0, min(100, round((1 - (rem / (r.get("total_seconds") or 1))) * 100))),
                })
        self.timer_records = valid_records
        return active

    def cancel_timer(self, timer_id: str) -> bool:
        """Cancels an active timer by its unique ID."""
        for r in list(self.timer_records):
            if r.get("id") == timer_id:
                t = r.get("timer_obj")
                if t:
                    try:
                        t.cancel()
                    except Exception:
                        pass
                if t in self.active_timers:
                    try:
                        self.active_timers.remove(t)
                    except Exception:
                        pass
                self.timer_records.remove(r)
                self._log_event("timer", f"Canceled timer {timer_id}")
                return True
        return False

    def cancel_all_timers(self) -> int:
        """Cancels all currently active timers."""
        count = 0
        for r in list(self.timer_records):
            t = r.get("timer_obj")
            if t:
                try:
                    t.cancel()
                except Exception:
                    pass
            count += 1
        self.active_timers.clear()
        self.timer_records.clear()
        self._log_event("timer", f"Canceled all {count} timers")
        return count

    def _log_event(self, category: str, note: str) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "note": note,
        }
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


# Global singleton
tools = AgentTools()
