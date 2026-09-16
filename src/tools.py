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
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")
TIMERS_FILE = os.path.join(DATA_DIR, "timers.json")
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
        self.timer_records: List[Dict[str, Any]] = self._load_timers_from_disk()
        self._restore_pending_timers()
        self.active_reminders: List[threading.Timer] = []
        self.reminder_records: List[Dict[str, Any]] = self._load_reminders_from_disk()
        self._restore_pending_reminders()

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

    def update_assistant_name(self, new_name: str) -> str:
        """Updates the assistant's own name across assistant.json and config.json."""
        cleaned_name = new_name.strip().capitalize()
        if not cleaned_name:
            return "I couldn't catch the new name."

        # 1. Update data/assistant.json
        try:
            from src.memory import memory
            memory.update_assistant(name=cleaned_name)
        except Exception as e:
            print(f"[Tools] Failed to update assistant.json: {e}")

        # 2. Update config.json
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            cfg_data["assistant_name"] = cleaned_name
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg_data, f, indent=2)
        except Exception as e:
            print(f"[Tools] Failed to update config.json: {e}")

        # 3. Log event
        self._log_event("identity", f"Assistant name changed to '{cleaned_name}'")
        return f"Got it. My name is now {cleaned_name}. You can call me {cleaned_name} from now on."

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

            # Push to undo stack
            try:
                from src.action_guards import action_guards
                def _undo_remember():
                    try:
                        with open(MEMORY_FILE, "r", encoding="utf-8") as f_in:
                            d = json.load(f_in)
                        if cleaned_fact in d.get("learned_facts", []):
                            d["learned_facts"].remove(cleaned_fact)
                            with open(MEMORY_FILE, "w", encoding="utf-8") as f_out:
                                json.dump(d, f_out, indent=2)
                            return True
                    except Exception:
                        pass
                    return False
                action_guards.push_undo(f"remember_{int(time.time())}", f"remembering that {cleaned_fact}", _undo_remember)
            except Exception:
                pass

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
        timer_id = f"timer_{int(end_timestamp)}_{len(self.timer_records)}"
        record = {
            "id": timer_id,
            "label": label,
            "display_time": display_time,
            "total_seconds": seconds,
            "end_timestamp": end_timestamp,
            "created_at": datetime.now().isoformat(),
        }
        self.timer_records.append(record)
        self._save_timers_to_disk()

        def _timer_callback():
            print(f"\n⏰ [ALARM TRIGGERED]: {label.capitalize()} for {display_time} is up!")
            try:
                self.timer_records = [r for r in self.timer_records if r.get("id") != record["id"]]
                self._save_timers_to_disk()
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

        # Push to undo stack
        try:
            from src.action_guards import action_guards
            action_guards.push_undo(timer_id, f"setting {label} for {display_time}", lambda: self.cancel_timer(timer_id))
        except Exception:
            pass

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
            self._save_timers_to_disk()

            def _clock_callback():
                print(f"\n⏰ [CLOCK ALARM TRIGGERED]: {label.capitalize()} for {display_target}!")
                try:
                    self.timer_records = [r for r in self.timer_records if r.get("id") != clock_record["id"]]
                    self._save_timers_to_disk()
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
        if len(valid_records) != len(self.timer_records):
            self.timer_records = valid_records
            self._save_timers_to_disk()
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
                self._save_timers_to_disk()
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
        self._save_timers_to_disk()
        self._log_event("timer", f"Canceled all {count} timers")
        return count

    def _save_timers_to_disk(self) -> None:
        try:
            clean = []
            for r in self.timer_records:
                clean.append({k: v for k, v in r.items() if k != "timer_obj"})
            with open(TIMERS_FILE, "w", encoding="utf-8") as f:
                json.dump(clean, f, indent=2)
        except Exception as e:
            print(f"[Tools] Error saving timers.json: {e}")

    def _load_timers_from_disk(self) -> List[Dict[str, Any]]:
        if not os.path.exists(TIMERS_FILE):
            return []
        try:
            with open(TIMERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _restore_pending_timers(self) -> None:
        """Restores pending future timers on startup."""
        now_ts = time.time()
        active_records = []
        for r in self.timer_records:
            end_ts = r.get("end_timestamp", 0)
            if end_ts > now_ts:
                diff_secs = end_ts - now_ts
                label = r.get("label", "alarm")
                disp = r.get("display_time", f"{int(diff_secs)}s")

                def _timer_cb(rec=r, lbl=label, dsp=disp):
                    print(f"\n⏰ [ALARM TRIGGERED]: {lbl.capitalize()} for {dsp} is up!")
                    try:
                        self.timer_records = [x for x in self.timer_records if x.get("id") != rec.get("id")]
                        self._save_timers_to_disk()
                    except Exception:
                        pass
                    play_alarm_sound(repeats=2)
                    time.sleep(0.3)
                    speak(f"Your {lbl} for {dsp} is up.", interruptible=False)

                t = threading.Timer(diff_secs, _timer_cb)
                t.daemon = True
                r["timer_obj"] = t
                t.start()
                self.active_timers.append(t)
                active_records.append(r)

        self.timer_records = active_records
        self._save_timers_to_disk()

    # =============================================================
    # MEMORY SEARCH & NATURAL RECALL
    # =============================================================
    def search_facts(self, query: str) -> Optional[str]:
        """Searches learned facts in memory.json for answers to user queries (e.g. 'where is my pen', 'what is my password')."""
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                mem_data = json.load(f)
            facts = mem_data.get("learned_facts", [])
            if not facts:
                return None

            clean_q = query.strip().lower()
            # Extract key nouns/terms from query (remove question filler)
            stop_words = {"what", "is", "my", "the", "where", "did", "i", "put", "keep", "leave", "tell", "you", "about", "a", "an", "do", "know", "can", "find", "for", "of", "to", "in", "on", "at"}
            tokens = [w for w in re.findall(r'\b[a-zA-Z0-9_\'-]+\b', clean_q) if w not in stop_words and len(w) > 2]

            if not tokens:
                return None

            # Score each fact by matching tokens
            best_fact = None
            best_score = 0

            for fact in facts:
                fact_lower = fact.lower()
                score = sum(1 for t in tokens if t in fact_lower)
                if score > best_score:
                    best_score = score
                    best_fact = fact

            if best_fact and best_score > 0:
                # Clean up stored prefix if any (e.g. "User context: ...")
                clean_fact = re.sub(r'^User context:\s*', '', best_fact, flags=re.I)
                return f"According to what you told me: {clean_fact}."
            return None
        except Exception as e:
            print(f"[Tools] Error searching facts: {e}")
            return None

    # =============================================================
    # REMINDERS ENGINE & SCHEDULER
    # =============================================================
    def parse_and_set_reminder(self, user_text: str) -> Optional[str]:
        """Parses natural language reminder requests and schedules them."""
        import datetime as dt_mod
        raw = user_text.strip()
        now = datetime.now()

        # Clean decimal timestamps from speech recognition (e.g., "5.0 at the pm", "5.0 pm" -> "5:00 pm")
        cleaned = re.sub(r'(\d{1,2})\.0\s*(?:at\s+the\s+|at\s+)?(am|pm)', r'\1:00 \2', raw, flags=re.I)
        cleaned = re.sub(r'(\d{1,2})\.00\s*(am|pm)', r'\1:00 \2', cleaned, flags=re.I)
        # Strip leading trigger/assistant wrapper phrases
        cleaned = re.sub(r'^(?:(?:hey|hi|hello|nova|tars|assistant)\s*[,.]*\s*)+', '', cleaned, flags=re.I)

        # 1. Relative duration: e.g. "remind me in 15 minutes to call mom" or "remind me to call mom in 15 minutes"
        rel_match = re.search(
            r"(?:remind\s+(?:me\s+)?|set\s+a\s+reminder\s+(?:for|to|about)?\s*|schedule\s+a\s+reminder\s+(?:for|to|about)?\s*)(?:in\s+(.+?)\s+(?:to|about)\s+(.+)|to\s+(.+?)\s+in\s+(.+))",
            cleaned,
            re.IGNORECASE,
        )
        if rel_match:
            from src.duration_parser import extract_duration_seconds
            if rel_match.group(1) and rel_match.group(2):
                dur_str = rel_match.group(1)
                task = rel_match.group(2).strip()
            else:
                task = rel_match.group(3).strip()
                dur_str = rel_match.group(4)

            secs = extract_duration_seconds(dur_str)
            if secs and secs > 0:
                target_dt = now + dt_mod.timedelta(seconds=secs)
                disp_time = target_dt.strftime("%I:%M %p").lstrip("0")
                mins = round(secs / 60, 1)
                unit_display = f"{int(secs)} seconds" if secs < 60 else (f"{int(mins)} minute" if mins == 1 else f"{mins} minutes")
                return self._schedule_reminder(task=task, target_timestamp=target_dt.timestamp(), display_str=f"in {unit_display} ({disp_time})")

        # 2. Specific clock time and day (flexible order)
        # Match time token e.g. "at 5pm", "at 5:00 pm", "5pm", "5:00 pm", "5 am", "17:00"
        time_token_match = re.search(r'\b(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2})\b', cleaned, re.I)
        # Match day token e.g. "tomorrow", "today", "on Friday", "Friday"
        day_token_match = re.search(r'\b(?:on\s+)?(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', cleaned, re.I)

        if time_token_match or day_token_match:
            time_str = time_token_match.group(1).strip().upper() if time_token_match else "9:00 AM"
            day_str = day_token_match.group(1).lower() if day_token_match else ""

            target_time = None
            for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M"):
                try:
                    target_time = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue

            if not target_time:
                try:
                    target_time = datetime.strptime(f"{time_str}:00", "%H:%M")
                except Exception:
                    target_time = datetime.strptime("9:00 AM", "%I:%M %p")

            target_dt = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)

            if "tomorrow" in day_str:
                target_dt += dt_mod.timedelta(days=1)
            elif day_str and day_str != "today":
                days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                if day_str in days_of_week:
                    target_weekday = days_of_week.index(day_str)
                    current_weekday = now.weekday()
                    days_ahead = (target_weekday - current_weekday) % 7
                    if days_ahead == 0 and target_dt <= now:
                        days_ahead = 7
                    target_dt += dt_mod.timedelta(days=days_ahead)
            elif target_dt <= now:
                target_dt += dt_mod.timedelta(days=1)

            # Extract clean task description
            task = cleaned
            task = re.sub(r'\b(?:on\s+)?(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', ' ', task, flags=re.I)
            task = re.sub(r'\b(?:at\s+)?(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2})\b', ' ', task, flags=re.I)
            task = re.sub(r'^(?:(?:please\s+|can\s+you\s+|i\s+want\s+(?:you\s+)?to\s+|i\s+need\s+(?:you\s+)?to\s+|set\s+a\s+reminder\s+(?:for|to|about)?|schedule\s+a\s+reminder\s+(?:for|to|about)?|create\s+a\s+reminder\s+(?:for|to|about)?|add\s+a\s+reminder\s+(?:for|to|about)?|remind\s+me\s+(?:to|about)?|reminder\s+(?:for|to|about)?)\s*)+', '', task, flags=re.I)
            task = re.sub(r'^(?:to|about|for|that)\s+', '', task.strip(), flags=re.I)
            task = re.sub(r'\s+', ' ', task).strip()
            if not task:
                task = "scheduled reminder"

            display_dt = target_dt.strftime("%A, %b %d at %I:%M %p").replace(" 0", " ")
            return self._schedule_reminder(task=task, target_timestamp=target_dt.timestamp(), display_str=display_dt)

        return None

    def _schedule_reminder(self, task: str, target_timestamp: float, display_str: str) -> str:
        diff_secs = max(0.5, target_timestamp - time.time())
        rem_id = f"rem_{int(target_timestamp)}_{len(self.reminder_records)}"
        record = {
            "id": rem_id,
            "task": task,
            "target_timestamp": target_timestamp,
            "display_str": display_str,
            "created_at": datetime.now().isoformat(),
            "completed": False,
        }
        self.reminder_records.append(record)
        self._save_reminders_to_disk()

        def _reminder_cb():
            print(f"\n🔔 [REMINDER TRIGGERED]: {task}!")
            try:
                record["completed"] = True
                self._save_reminders_to_disk()
            except Exception:
                pass
            play_alarm_sound(repeats=2)
            time.sleep(0.3)
            alert_msg = f"Reminder: {task}."
            speak(alert_msg, interruptible=False)

        t = threading.Timer(diff_secs, _reminder_cb)
        t.daemon = True
        record["timer_obj"] = t
        t.start()
        self.active_reminders.append(t)

        self._log_event("reminder", f"Set reminder to '{task}' ({display_str})")
        return f"Got it. I'll remind you to {task} {display_str}."

    def get_active_reminders(self) -> List[Dict[str, Any]]:
        """Returns list of pending reminders that have not expired yet."""
        now_ts = time.time()
        active = []
        for r in self.reminder_records:
            if not r.get("completed", False) and r.get("target_timestamp", 0) > now_ts:
                active.append(r)
        return active

    def get_active_reminders_summary(self) -> str:
        """Returns clean text summary of all active upcoming reminders."""
        active = self.get_active_reminders()
        if not active:
            return "You have no upcoming reminders scheduled right now."
        if len(active) == 1:
            r = active[0]
            return f"You have 1 upcoming reminder: {r.get('task')} on {r.get('display_str')}."
        items = [f"{r.get('task')} ({r.get('display_str')})" for r in active]
        return f"You have {len(active)} upcoming reminders: {', '.join(items)}."

    def cancel_reminder(self, rem_id: str) -> bool:
        """Cancels a specific reminder by its ID."""
        for r in self.reminder_records:
            if r.get("id") == rem_id and not r.get("completed", False):
                r["completed"] = True
                if "timer_obj" in r and r["timer_obj"]:
                    try:
                        r["timer_obj"].cancel()
                    except Exception:
                        pass
                self._save_reminders_to_disk()
                self._log_event("reminder", f"Cancelled reminder '{r.get('task')}'")
                return True
        return False

    def cancel_all_reminders(self) -> int:
        """Cancels all active reminders."""
        count = 0
        for t in self.active_reminders:
            try:
                t.cancel()
            except Exception:
                pass
            count += 1
        self.active_reminders.clear()
        for r in self.reminder_records:
            r["completed"] = True
        self._save_reminders_to_disk()
        self._log_event("reminder", f"Canceled all {count} active reminders")
        return count

    def _save_reminders_to_disk(self) -> None:
        try:
            # Strip non-serializable timer objects before saving
            clean_records = []
            for r in self.reminder_records:
                clean_records.append({k: v for k, v in r.items() if k != "timer_obj"})
            with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(clean_records, f, indent=2)
        except Exception as e:
            print(f"[Tools] Error saving reminders.json: {e}")

    def _load_reminders_from_disk(self) -> List[Dict[str, Any]]:
        if not os.path.exists(REMINDERS_FILE):
            return []
        try:
            with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _restore_pending_reminders(self) -> None:
        """Restores pending future reminders on startup."""
        now_ts = time.time()
        for r in self.reminder_records:
            target_ts = r.get("target_timestamp", 0)
            if not r.get("completed", False) and target_ts > now_ts:
                diff_secs = target_ts - now_ts
                task = r.get("task", "Reminder")

                def _cb(rec=r, tsk=task):
                    print(f"\n🔔 [REMINDER TRIGGERED]: {tsk}!")
                    try:
                        rec["completed"] = True
                        self._save_reminders_to_disk()
                    except Exception:
                        pass
                    play_alarm_sound(repeats=2)
                    time.sleep(0.3)
                    speak(f"Reminder: {tsk}.", interruptible=False)

                t = threading.Timer(diff_secs, _cb)
                t.daemon = True
                r["timer_obj"] = t
                t.start()
                self.active_reminders.append(t)

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

    # =============================================================
    # AGENTIC PRIORITY 2 TOOLS
    # =============================================================
    def set_ui_theme(self, theme_name: str) -> str:
        """Changes the web UI theme (e.g. 'midnight', 'emerald', 'cyberpunk', 'light', 'dark')."""
        clean_theme = theme_name.lower().strip()
        valid_themes = {"midnight", "emerald", "cyberpunk", "light", "dark", "amber", "nord"}
        if clean_theme not in valid_themes:
            clean_theme = "midnight" if "dark" in clean_theme else "light"

        from src.memory import memory
        state = memory.load_state()
        state.setdefault("ui", {})["theme"] = clean_theme
        memory.save_state(state)
        self._log_event("theme", f"Switched UI theme to '{clean_theme}'")
        return f"Switched theme to {clean_theme.capitalize()}."

    def set_visual_engine(self, engine_mode: str) -> str:
        """Sets dashboard voice visualizer to '3d' (Particle Orb) or '2d' (Concentric Reactor Core)."""
        clean = engine_mode.lower().strip()
        is_3d = "3d" in clean or "orb" in clean or "three" in clean
        target_mode = "3d" if is_3d else "2d"

        from src.memory import memory
        state = memory.load_state()
        state.setdefault("ui", {})["visual_engine"] = target_mode
        memory.save_state(state)
        self._log_event("ui_engine", f"Switched visual engine to '{target_mode}'")
        desc = "3D Particle Orb" if is_3d else "2D Concentric Core"
        return f"Switched dashboard visual engine to {desc}."

    def switch_dashboard_tab(self, tab_identifier: str) -> str:
        """Switches the active dashboard view/tab (e.g., 'overview', 'live display', 'alarms', 'settings', 'dossier')."""
        clean = tab_identifier.lower().strip()
        tab_map = {
            "live display": ("tab-livedisplay", "Live Display"),
            "livedisplay": ("tab-livedisplay", "Live Display"),
            "display": ("tab-livedisplay", "Live Display"),
            "overview": ("tab-overview", "Assistant Overview"),
            "status": ("tab-overview", "Assistant Overview"),
            "home": ("tab-overview", "Assistant Overview"),
            "dossier": ("tab-user-profile", "Resident Dossier"),
            "profile": ("tab-user-profile", "Resident Dossier"),
            "memory": ("tab-user-profile", "Resident Dossier"),
            "alarms": ("tab-alarms", "Alarms & Timers"),
            "timers": ("tab-alarms", "Alarms & Timers"),
            "alarm": ("tab-alarms", "Alarms & Timers"),
            "timer": ("tab-alarms", "Alarms & Timers"),
            "settings": ("tab-config", "Settings"),
            "config": ("tab-config", "Settings"),
            "configuration": ("tab-config", "Settings"),
            "chat": ("tab-chat", "Chat Console"),
            "console": ("tab-chat", "Chat Console"),
            "architecture": ("tab-about-ai", "AI Architecture"),
            "about": ("tab-about-ai", "AI Architecture"),
        }
        matched = None
        for k, v in tab_map.items():
            if k in clean:
                matched = v
                break
        if not matched:
            matched = ("tab-livedisplay", "Live Display")

        tab_id, title = matched
        from src.memory import memory
        state = memory.load_state()
        state.setdefault("ui", {})["active_tab"] = tab_id
        state["ui"]["tab_updated_at"] = time.time()
        memory.save_state(state)
        self._log_event("ui_tab", f"Navigated to '{tab_id}'")
        return f"Switched dashboard to {title}."

    def set_kiosk_mode(self, enabled: bool) -> str:
        """Toggles fullscreen ambient kiosk mode on the dashboard."""
        from src.memory import memory
        state = memory.load_state()
        state.setdefault("ui", {})["kiosk_mode"] = bool(enabled)
        memory.save_state(state)
        self._log_event("ui_kiosk", f"Set kiosk mode to {enabled}")
        return "Entered fullscreen kiosk mode." if enabled else "Exited kiosk mode."

    def get_system_health(self) -> str:
        """Queries CPU, memory, uptime, and battery health via platform adapter."""
        from src.platform_adapter import platform_adapter
        metrics = platform_adapter.get_system_metrics()
        battery = platform_adapter.get_battery_status()
        wifi = platform_adapter.get_wifi_status()

        parts = [f"OS: {metrics.get('os_name', 'System')}."]
        if metrics.get("load_average_1m") is not None:
            parts.append(f"1-min load average is {metrics.get('load_average_1m')}.")
        if battery.get("has_battery") and battery.get("percent") is not None:
            parts.append(f"Battery: {battery.get('percent')}% ({battery.get('power_source')}).")
        else:
            parts.append("Power: Connected to AC.")
        if wifi.get("connected"):
            parts.append(f"Wi-Fi: Connected to {wifi.get('ssid')}.")
        return " ".join(parts)

    def get_wifi_info(self) -> str:
        """Queries active Wi-Fi connection and signal status."""
        from src.platform_adapter import platform_adapter
        wifi = platform_adapter.get_wifi_status()
        if wifi.get("connected"):
            sig = wifi.get("signal_quality", "Good")
            return f"Wi-Fi is connected to '{wifi.get('ssid')}' with {sig} signal."
        return "Wi-Fi is currently disconnected or inactive."

    def get_phone_status(self) -> str:
        """Queries connected Android device status via ADB."""
        from src.android_bridge import android_bridge
        status = android_bridge.get_phone_status()
        if not status.get("available"):
            return "Android phone bridge (ADB) is not installed on this server."
        if not status.get("connected"):
            return "No Android phone is connected via USB or Wi-Fi ADB right now."
        if not status.get("authorized"):
            return status.get("message", "Phone connected but unauthorized.")
        return status.get("summary", "Phone connected and ready.")

    def make_phone_call(self, target: str) -> str:
        """Places a phone call using connected Android device via ADB."""
        from src.android_bridge import android_bridge
        res = android_bridge.initiate_phone_call(target)
        if res.get("ok"):
            self._log_event("phone", f"Initiated phone call to {res.get('phone_number')}")
            return res.get("message", f"Calling {target} on your phone.")
        return f"Couldn't place phone call: {res.get('error', 'Phone bridge unavailable')}."

    def schedule_sleep_and_return(self, duration_seconds: float) -> str:
        """Turns off assistant core and schedules automated awakening after downtime."""
        from src.supervisor import supervisor
        return supervisor.schedule_sleep_and_return(duration_seconds)

    def trigger_routine(self, routine_name: str) -> str:
        """Executes a smart-home routine."""
        from src.routines import routine_engine
        return routine_engine.execute_routine(routine_name)

    def undo_last_action(self) -> str:
        """Reverses the most recent mutating action from the undo stack."""
        from src.action_guards import action_guards
        res = action_guards.pop_and_undo()
        return res.get("message", "Nothing to undo.")

    def control_lights(self, action: str = "turn on") -> str:
        from src.device_inventory import device_inventory
        if not device_inventory.is_connected("lights"):
            return device_inventory.get_grounded_refusal("smart lights", action)
        return f"Lights {action}ed."

    def control_ac(self, action: str = "turn on") -> str:
        from src.device_inventory import device_inventory
        if not device_inventory.is_connected("ac"):
            return device_inventory.get_grounded_refusal("air conditioner", action)
        return f"AC {action}ed."

    def control_tv(self, action: str = "turn on") -> str:
        from src.device_inventory import device_inventory
        if not device_inventory.is_connected("tv"):
            return device_inventory.get_grounded_refusal("TV", action)
        return f"TV {action}ed."

    def get_weather_and_location(self) -> str:
        """Returns the current location, timezone, and live weather report."""
        from src.memory import memory
        mem = memory.load_memory()
        prof = mem.get("profile", {})
        loc = prof.get("location", "Nigeria")
        tz = prof.get("timezone", "Africa/Lagos")
        weather = prof.get("weather", {})
        temp = weather.get("temperature") or weather.get("temp", "28°C")
        desc = weather.get("description") or weather.get("desc", "Partly Cloudy")
        return f"Current location: {loc} ({tz}). Weather: {temp}, {desc}."


# Global singleton
tools = AgentTools()
