import json
import os
import re
from datetime import datetime
from typing import Optional, Tuple

from src.brain import brain
from src.memory import memory
from src.tools import tools

CHAT_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "chat_history.json",
)


class HomeAgent:
    def __init__(self, history_file: str = CHAT_HISTORY_FILE):
        self.history_file = history_file
        self.persistent_history = self._load_chat_history()

    def _load_chat_history(self) -> list:
        """Loads previous conversation turns from disk."""
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_turn(self, role: str, content: str) -> None:
        """Appends a turn to the persistent chat history."""
        self.persistent_history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        })
        # Keep recent 40 turns
        if len(self.persistent_history) > 40:
            self.persistent_history = self.persistent_history[-40:]

        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.persistent_history, f, indent=2)
        except Exception as e:
            print(f"[Agent] Failed to save chat history: {e}")

    def process_message(self, user_text: str) -> str:
        """
        Agentic Intent Router:
        1. Checks for tool commands (identity, memory, timers).
        2. If command matched, executes tool immediately with 100% precision.
        3. If casual conversation, passes to LLM with full context and saves to persistent chat log.
        """
        cleaned = user_text.strip().lower()
        self._save_turn("user", user_text)

        # -------------------------------------------------------------
        # TOOL 1: Change Preferred Name
        # e.g. "I want you to address me as Sam", "Call me Alex"
        # -------------------------------------------------------------
        name_match = re.search(
            r"(?:address me as|call me|my name is)\s+([a-zA-Z]+)",
            cleaned,
            re.IGNORECASE,
        )
        if name_match:
            new_name = name_match.group(1)
            response = tools.update_preferred_name(new_name)
            brain.reset_history()  # Refresh LLM system prompt with new name
            self._save_turn("assistant", response)
            return response

        # -------------------------------------------------------------
        # TOOL 2: Remember Explicit Facts
        # e.g. "Remember that I don't have money for chicken soup"
        # -------------------------------------------------------------
        remember_match = re.search(
            r"(?:remember that|remember this\s*[:-]?|you need to remember that|you need to remember|save this fact\s*[:-]?)\s+(.*)",
            user_text,
            re.IGNORECASE,
        )
        if remember_match:
            fact_content = remember_match.group(1).strip()
            # Clean trailing punctuation
            fact_content = re.sub(r"[.!?]+$", "", fact_content)
            response = tools.remember_fact(fact_content)
            brain.reset_history()  # Refresh LLM with new learned fact
            self._save_turn("assistant", response)
            return response

        # -------------------------------------------------------------
        # TOOL 3: Set Timer / Alarm with Sound
        # e.g. "Play an alarm sound in 20 minutes", "Set alarm for 10 seconds", "Alarm at 7:30 am"
        # -------------------------------------------------------------
        # 3a. Relative duration (seconds / minutes / hours)
        duration_match = re.search(
            r"(?:play (?:an? )?alarm(?: sound)? in|set (?:an? )?alarm for|ring (?:my )?alarm in|set (?:a )?timer for|alarm in|timer for|wake me up in)\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)",
            cleaned,
            re.IGNORECASE,
        )
        if duration_match:
            value = float(duration_match.group(1))
            unit = duration_match.group(2).lower()
            if "sec" in unit:
                total_seconds = value
            elif "hour" in unit or "hr" in unit:
                total_seconds = value * 3600
            else:
                total_seconds = value * 60

            label = "alarm" if ("alarm" in cleaned or "wake" in cleaned) else "timer"
            response = tools.set_timer(total_seconds, label=label)
            self._save_turn("assistant", response)
            return response

        # 3b. Clock time alarm (e.g. "at 7:30 am", "for 8 pm")
        clock_match = re.search(
            r"(?:set (?:an? )?alarm (?:for|at)|alarm (?:at|for)|wake me up (?:at|for))\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})",
            cleaned,
            re.IGNORECASE,
        )
        if clock_match:
            time_str = clock_match.group(1).strip()
            response = tools.set_clock_alarm(time_str, label="alarm")
            self._save_turn("assistant", response)
            return response

        # -------------------------------------------------------------
        # TOOL 4: Query Active Timers
        # e.g. "How much time is left?", "Any timers running?", "Check timers"
        # -------------------------------------------------------------
        if re.search(r"\b(how much time is left|active timers?|any timers?|check timers?|status of (?:the )?timer|what timer|timers? running)\b", cleaned):
            active = tools.get_active_timers()
            if not active:
                reply = "You don't have any active timers running right now."
            elif len(active) == 1:
                t = active[0]
                rem_mins = int(t['remaining_seconds'] // 60)
                rem_secs = int(t['remaining_seconds'] % 60)
                time_str = f"{rem_mins}m {rem_secs}s" if rem_mins > 0 else f"{rem_secs}s"
                reply = f"You have 1 active {t['label']} ({t['display_time']}) with {time_str} remaining."
            else:
                details = []
                for t in active:
                    rem_mins = int(t['remaining_seconds'] // 60)
                    rem_secs = int(t['remaining_seconds'] % 60)
                    time_str = f"{rem_mins}m {rem_secs}s" if rem_mins > 0 else f"{rem_secs}s"
                    details.append(f"{t['label']} ({t['display_time']}, {time_str} left)")
                reply = f"You have {len(active)} active timers: {', '.join(details)}."
            self._save_turn("assistant", reply)
            return reply

        # -------------------------------------------------------------
        # TOOL 5: Cancel Timers / Alarms
        # e.g. "Cancel timer", "Stop the alarm", "Clear timers"
        # -------------------------------------------------------------
        if re.search(r"\b(cancel (?:the |all )?timers?|stop (?:the |all )?timers?|clear (?:the |all )?timers?|cancel (?:the |all )?alarms?|stop (?:the |all )?alarms?)\b", cleaned):
            count = tools.cancel_all_timers()
            reply = "I've canceled your active timers." if count > 0 else "There are no active timers to cancel."
            self._save_turn("assistant", reply)
            return reply

        # -------------------------------------------------------------
        # TOOL 6: "What do you know about me?"
        # -------------------------------------------------------------
        if re.search(r"\b(what do you know about me|what do you remember about me|who am i|tell me about me|what shows do i like|what do i like to watch)\b", cleaned):
            mem_data = memory.load_memory()
            name = mem_data.get("profile", {}).get("preferred_name", "Timilehin")
            series = mem_data.get("preferences", {}).get("entertainment", {}).get("favorite_series", [])
            facts = mem_data.get("learned_facts", [])
            
            summary = f"You are {name}. You love high-concept sci-fi and fantasy shows like {', '.join(series)}."
            if facts:
                summary += f" I also remember: {'; '.join(facts[-3:])}."
            self._save_turn("assistant", summary)
            return summary

        # -------------------------------------------------------------
        # TOOL 7: "Who are you?" / About the AI
        # -------------------------------------------------------------
        if re.search(r"\b(who are you|what are you|tell me about yourself|what is your name)\b", cleaned):
            asst_data = memory.load_assistant()
            name = asst_data.get("name", "Nova")
            reply = f"I am {name}, your private local smart home assistant. I run 100% offline on your machine with a local Llama 3.2 3B brain, keeping all your data completely private."
            self._save_turn("assistant", reply)
            return reply

        # -------------------------------------------------------------
        # GENERAL CONVERSATION (Passed to LLM Brain)
        # -------------------------------------------------------------
        reply = brain.chat(user_text)
        self._save_turn("assistant", reply)
        return reply


# Global singleton
agent = HomeAgent()
