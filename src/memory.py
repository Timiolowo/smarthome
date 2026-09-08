import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
ASSISTANT_FILE = os.path.join(DATA_DIR, "assistant.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
LOG_FILE = os.path.join(DATA_DIR, "memory_log.jsonl")


class MemoryManager:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.memory_file = os.path.join(data_dir, "memory.json")
        self.assistant_file = os.path.join(data_dir, "assistant.json")
        self.state_file = os.path.join(data_dir, "state.json")
        self.log_file = os.path.join(data_dir, "memory_log.jsonl")
        os.makedirs(self.data_dir, exist_ok=True)

    def load_assistant(self) -> Dict[str, Any]:
        """Loads the AI assistant's identity, name, and behavioral rules."""
        if not os.path.exists(self.assistant_file):
            return {
                "name": "Nova",
                "role": "Personal Smart Home Assistant",
                "personality": {"tone": "Warm, natural, direct, intelligent"},
                "behavior_rules": [
                    "Be concise by default, but answer completely when lists or multiple reasons are requested.",
                    "Never be romantic. No pet names.",
                    "Never discuss corporate or office work."
                ]
            }
        try:
            with open(self.assistant_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Memory] Error reading assistant.json: {e}")
            return {}

    def load_memory(self) -> Dict[str, Any]:
        """Loads static profile, preferences, and boundaries for Timilehin."""
        if not os.path.exists(self.memory_file):
            return {}
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Memory] Error reading memory.json: {e}")
            return {}

    def load_state(self) -> Dict[str, Any]:
        """Loads live household state (media, power, presence, climate)."""
        if not os.path.exists(self.state_file):
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Memory] Error reading state.json: {e}")
            return {}

    def save_state(self, state: Dict[str, Any]) -> None:
        """Saves updated live household state."""
        state["system"] = state.get("system", {})
        state["system"]["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"[Memory] Error saving state.json: {e}")

    def update_presence(self, is_home: bool) -> None:
        """Updates user presence state and records timestamp."""
        state = self.load_state()
        presence = state.setdefault("presence", {})
        now = datetime.now().isoformat()
        
        if is_home and not presence.get("is_user_home"):
            presence["last_arrival"] = now
            self.log_event("presence", f"Timilehin arrived home at {now}")
        elif not is_home and presence.get("is_user_home"):
            presence["last_departure"] = now
            self.log_event("presence", f"Timilehin left home at {now}")

        presence["is_user_home"] = is_home
        self.save_state(state)

    def update_last_watched(
        self,
        title: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        timestamp_minutes: Optional[int] = None,
    ) -> None:
        """Updates currently watched show position."""
        state = self.load_state()
        media = state.setdefault("media", {})
        media["last_watched"] = {
            "title": title,
            "season": season,
            "episode": episode,
            "timestamp_minutes": timestamp_minutes,
            "updated_at": datetime.now().isoformat(),
        }
        self.save_state(state)
        self.log_event("entertainment", f"Paused {title} (S{season}E{episode}) at {timestamp_minutes} mins.")

    def log_event(self, category: str, note: str) -> None:
        """Appends an episodic memory event to the JSONL log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "note": note,
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"[Memory] Error writing to memory_log.jsonl: {e}")

    def get_recent_logs(self, limit: int = 50, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns the most recent events from memory_log.jsonl in reverse chronological order."""
        if not os.path.exists(self.log_file):
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            continue
        except Exception as e:
            print(f"[Memory] Error reading memory_log.jsonl: {e}")
            return []

        if category and category.lower() != "all":
            entries = [e for e in entries if e.get("category", "").lower() == category.lower()]

        return list(reversed(entries[-limit:]))

    def update_assistant_runtime(
        self,
        runtime_state: str,
        last_heard: Optional[str] = None,
        last_reply: Optional[str] = None,
    ) -> None:
        """Updates the live assistant state in state.json for HUD and kiosk views."""
        state = self.load_state()
        asst = state.setdefault("assistant_runtime", {
            "state": "IDLE",
            "last_heard": "",
            "last_reply": "",
            "updated_at": datetime.now().isoformat(),
        })
        asst["state"] = runtime_state
        if last_heard is not None:
            asst["last_heard"] = last_heard
        if last_reply is not None:
            asst["last_reply"] = last_reply
        asst["updated_at"] = datetime.now().isoformat()
        self.save_state(state)

    def get_llm_system_prompt(self) -> str:
        """Generates the system prompt context using assistant.json and memory.json."""
        assistant = self.load_assistant()
        memory = self.load_memory()
        state = self.load_state()

        ai_name = assistant.get("name", "Nova")
        ai_role = assistant.get("role", "Smart Home Assistant")
        rules = "\n".join(f"- {r}" for r in assistant.get("behavior_rules", []))

        profile = memory.get("profile", {})
        user_name = profile.get("preferred_name", "Timilehin")
        pref = memory.get("preferences", {})
        media = state.get("media", {}).get("last_watched", {})
        power = state.get("power", {})

        last_media_str = "None"
        if media.get("title"):
            last_media_str = f"{media.get('title')} (S{media.get('season')}E{media.get('episode')} at {media.get('timestamp_minutes')} mins)"

        grid_str = "Available" if power.get("grid_available") else "Out (Inverter Battery)"

        learned = memory.get("learned_facts", [])
        facts_str = f"- Learned Facts to Remember: {'; '.join(learned)}\n" if learned else ""

        return (
            f"You are {ai_name}, {user_name}'s {ai_role}.\n"
            f"BEHAVIOR RULES:\n"
            f"{rules}\n"
            f"- When greeted with 'Hello' or arriving, welcome {user_name} home in 1 short sentence.\n"
            f"- When asked a question, answer it directly and accurately. If asked for multiple items or reasons (e.g. 'give me 2 reasons'), provide exactly that number of points clearly.\n"
            f"Context:\n"
            f"- Favorite Series: {', '.join(pref.get('entertainment', {}).get('favorite_series', []))}\n"
            f"- Last watched: {last_media_str} | Grid power: {grid_str}\n"
            f"{facts_str}"
            f"Answer naturally without unnecessary fluff."
        )


# Global singleton
memory = MemoryManager()
