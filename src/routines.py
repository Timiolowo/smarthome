"""
Smart-Home Routines & Compound Command Execution Engine.
Provides multi-action automated routines (Good Morning, Bedtime, Focus, Movie Time)
and multi-intent sentence decomposition.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.memory import memory

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ROUTINES_FILE = os.path.join(DATA_DIR, "routines.json")


class RoutineEngine:
    DEFAULT_ROUTINES = {
        "good_morning": {
            "name": "Good Morning",
            "trigger_phrases": ["good morning routine", "start my day", "morning routine"],
            "description": "Greets user, reports time and active reminders.",
            "theme": "light",
        },
        "bedtime": {
            "name": "Bedtime / Goodnight",
            "trigger_phrases": ["bedtime routine", "goodnight routine", "going to sleep"],
            "description": "Wishes goodnight, ensures alarms are active.",
            "theme": "midnight",
        },
        "focus": {
            "name": "Focus Mode",
            "trigger_phrases": ["focus mode", "start focus session", "study routine"],
            "description": "Sets a 25-minute timer and enables focus theme.",
            "theme": "emerald",
            "timer_minutes": 25,
        },
        "movie_time": {
            "name": "Movie Time",
            "trigger_phrases": ["movie time", "movie mode", "start movie"],
            "description": "Sets cinematic ambient state and dark theme.",
            "theme": "cyberpunk",
        },
    }

    def __init__(self, routines_file: str = ROUTINES_FILE):
        self.routines_file = routines_file
        self.routines = self._load_routines()

    def _load_routines(self) -> Dict[str, Any]:
        if not os.path.exists(self.routines_file):
            self._save_routines(self.DEFAULT_ROUTINES)
            return dict(self.DEFAULT_ROUTINES)
        try:
            with open(self.routines_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return dict(self.DEFAULT_ROUTINES)

    def _save_routines(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.routines_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[RoutineEngine] Failed to save routines: {e}")

    def execute_routine(self, routine_key: str) -> str:
        """Executes the specified routine and returns voice summary."""
        key = routine_key.lower().strip().replace(" ", "_")
        routine = self.routines.get(key)
        if not routine:
            # Match by trigger phrase
            for r_key, r_data in self.routines.items():
                if any(phrase in routine_key.lower() for phrase in r_data.get("trigger_phrases", [])):
                    routine = r_data
                    key = r_key
                    break

        if not routine:
            return f"I couldn't find a routine matching '{routine_key}'."

        from src.tools import tools
        mem_data = memory.load_memory()
        user_name = mem_data.get("profile", {}).get("preferred_name", "Timilehin")

        results = []

        if key == "good_morning":
            now = datetime.now()
            time_str = now.strftime("%I:%M %p").lstrip("0")
            date_str = now.strftime("%A, %B %d")
            reminders = tools.get_active_reminders_summary()
            results.append(f"Good morning, {user_name}! It's {time_str} on {date_str}.")
            if "no upcoming reminders" not in reminders.lower():
                results.append(reminders)
            else:
                results.append("Your schedule is clear today.")

        elif key == "bedtime":
            results.append(f"Goodnight, {user_name}. Have a restful sleep.")
            active_timers = tools.get_active_timers()
            if active_timers:
                results.append(f"You have {len(active_timers)} alarm(s) set.")

        elif key == "focus":
            mins = routine.get("timer_minutes", 25)
            tools.set_timer(mins * 60, label="Focus session")
            results.append(f"Focus mode activated. Set a {mins}-minute timer. Let's get to work, {user_name}.")

        elif key == "movie_time":
            results.append(f"Movie mode engaged. Enjoy the show, {user_name}!")

        # Update theme if routine specifies one
        theme = routine.get("theme")
        if theme:
            tools.set_ui_theme(theme)

        memory.log_event("routine", f"Executed routine '{routine.get('name')}'")
        return " ".join(results)

    def decompose_compound_command(self, user_text: str) -> List[str]:
        """
        Decomposes compound sentences (e.g. 'set a timer for 10 minutes and switch theme to emerald')
        into individual executable intent strings.
        """
        # Split on strong conjunctions like " and then ", " and also ", ", then ", " and "
        parts = re.split(r"\b(?:and\s+then|and\s+also|,\s*then|\s+and\s+)\b", user_text, flags=re.IGNORECASE)
        commands = [p.strip() for p in parts if p.strip()]
        # Only treat as compound if at least 2 distinct action clauses exist
        if len(commands) > 1 and all(len(c.split()) >= 2 for c in commands):
            return commands
        return [user_text.strip()]


routine_engine = RoutineEngine()
