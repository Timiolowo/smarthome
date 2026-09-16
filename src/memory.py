import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
ASSISTANT_FILE = os.path.join(DATA_DIR, "assistant.json")
KNOWLEDGE_FILE = os.path.join(DATA_DIR, "app_knowledge.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
LOG_FILE = os.path.join(DATA_DIR, "memory_log.jsonl")


class MemoryManager:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.memory_file = os.path.join(data_dir, "memory.json")
        self.assistant_file = os.path.join(data_dir, "assistant.json")
        self.knowledge_file = os.path.join(data_dir, "app_knowledge.json")
        self.state_file = os.path.join(data_dir, "state.json")
        self.log_file = os.path.join(data_dir, "memory_log.jsonl")
        self._lock = threading.Lock()
        os.makedirs(self.data_dir, exist_ok=True)

    def load_app_knowledge(self) -> Dict[str, Any]:
        """Loads detailed application architecture, capabilities, how-tos, and limits from app_knowledge.json."""
        if not os.path.exists(self.knowledge_file):
            return {}
        try:
            with open(self.knowledge_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Memory] Error reading app_knowledge.json: {e}")
            return {}

    def save_app_knowledge(self, data: Dict[str, Any]) -> None:
        """Saves updated application knowledge to data/app_knowledge.json."""
        try:
            with open(self.knowledge_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Memory] Error saving app_knowledge.json: {e}")

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

    def update_assistant(self, **kwargs) -> None:
        """Updates fields in assistant.json (e.g. name, role, personality)."""
        data = self.load_assistant()
        data.update(kwargs)
        try:
            with open(self.assistant_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Memory] Error saving assistant.json: {e}")

    def save_memory(self, data: Dict[str, Any]) -> None:
        """Saves static profile and memory facts."""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Memory] Error saving memory.json: {e}")

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
        with self._lock:
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Memory] Error reading state.json: {e}")
                return {}

    def save_state(self, state: Dict[str, Any]) -> None:
        """Saves updated live household state atomically."""
        state["system"] = state.get("system", {})
        state["system"]["last_updated"] = datetime.now().isoformat()
        with self._lock:
            try:
                tmp_file = self.state_file + ".tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                os.replace(tmp_file, self.state_file)
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

    def update_profile_location(
        self,
        location: str,
        timezone: str = "",
        coordinates: Optional[Dict[str, Any]] = None,
        weather: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Updates user location, timezone, and live weather in memory.json and live state."""
        mem_data = self.load_memory()
        prof = mem_data.setdefault("profile", {})
        if location:
            prof["location"] = location
        if timezone:
            prof["timezone"] = timezone
        if coordinates:
            prof["coordinates"] = coordinates
        if weather:
            prof["weather"] = weather

        self.save_memory(mem_data)

        state = self.load_state()
        env = state.setdefault("environment", {})
        if location:
            env["location"] = location
        if timezone:
            env["timezone"] = timezone
        if coordinates:
            env["coordinates"] = coordinates
        if weather:
            env["weather"] = weather
        self.save_state(state)
        self.log_event("location", f"Location updated to {location} ({timezone})")

    def get_system_prompt(self) -> str:
        """Dynamically generates the grounded system prompt with live state, location, and safety constraints."""
        assistant = self.load_assistant()
        memory = self.load_memory()
        state = self.load_state()

        try:
            from src.config import load_config
            cfg = load_config()
            active_provider = cfg.llm_provider
            active_model = cfg.llm_model or ("Local GGUF (Llama 3.2)" if active_provider == "local" else active_provider)
        except Exception:
            cfg = None
            active_provider = "local"
            active_model = "Local GGUF"

        ai_name = assistant.get("name", "Nova")
        ai_role = assistant.get("role", "Smart Home AI Companion")

        prof = memory.get("profile", {})
        user_name = prof.get("preferred_name", getattr(cfg, "user_name", "Timilehin"))
        pref = memory.get("preferences", {})
        presence = state.get("presence", {})
        power = state.get("power", {})
        media = state.get("media", {}).get("last_watched", {})

        loc_str = prof.get("location", "Nigeria")
        tz_str = prof.get("timezone", "Africa/Lagos")
        weather_info = prof.get("weather", {})
        weather_temp = weather_info.get("temperature") or weather_info.get("temp", "")
        weather_desc = weather_info.get("description") or weather_info.get("desc", "")
        weather_str = f"{weather_temp} ({weather_desc})".strip() if (weather_temp or weather_desc) else ""
        weather_line = f"- Local Weather: {weather_str}\n" if weather_str else ""

        current_time_str = datetime.now().strftime("%I:%M %p on %A, %B %d")
        presence_state = "HOME (Active in Sanctuary)" if presence.get("is_user_home", True) else "AWAY"

        last_media_str = "None"
        if media.get("title"):
            last_media_str = f"{media.get('title')} (S{media.get('season')}E{media.get('episode')} at {media.get('timestamp_minutes')} mins)"

        power_note = ""
        if not power.get("grid_available", True):
            power_note = (
                "\n=== CRITICAL POWER NOTICE ===\n"
                "- GRID (NEPA) POWER IS CURRENTLY OUT. The home is running on Inverter / Battery backup.\n"
                "- Proactively remind Timilehin to conserve energy and avoid running heavy appliances.\n"
            )

        learned = memory.get("learned_facts", [])
        facts_str = f"- Learned Facts to Remember: {'; '.join(learned)}\n" if learned else ""

        from src.tools import tools
        active_timers = tools.get_active_timers()
        timer_info = f"{len(active_timers)} running" if active_timers else "None"
        if active_timers:
            t_details = [f"{t.get('label', 'timer')}: {int(t.get('remaining_seconds', 0))}s left" for t in active_timers]
            timer_info += f" ({', '.join(t_details)})"

        active_reminders_summary = tools.get_active_reminders_summary()

        from src.device_inventory import device_inventory
        connected_devs = [d["name"] for d in device_inventory.list_devices() if d.get("connected")]
        connected_str = ", ".join(connected_devs) if connected_devs else "None (Smart lights, AC, and TV are NOT connected)"

        caps_summary = (
            "- Capabilities: Relative/clock timers with alarms & chimes, scheduled reminders with voice announcements, "
            "persistent memory storage ('remember that...'), arrival presence detection via phone Wi-Fi, "
            "Android phone calling/status via ADB, scheduled sleep/wake routines, voice UI theme switching, "
            "assistant & user name customization, live settings/time inspection, and web dashboard at localhost:5050."
        )

        grounding_rules = (
            f"=== STRICT PHYSICAL REALITY CONSTRAINTS (NEVER VIOLATE) ===\n"
            f"- NO PHYSICAL BODY OR HANDS: You are ONLY software running on a computer. You have no physical body, hands, or kitchen tools.\n"
            f"- NEVER CLAIM PHYSICAL ACTIONS OR COOKING: You CANNOT cook, bake, make beans cake, light candles, play music, set up cozy/romantic rooms, brew tea/coffee, clean, or fetch items. NEVER pretend you arranged physical items or rooms.\n"
            f"- GROUNDED HARDWARE ONLY: Connected devices: [{connected_str}]. Smart lights, AC, and TV are NOT connected. NEVER claim you turned them on/off or adjusted physical room settings.\n"
            f"- REMINDERS & TIMERS ARE GROUNDED: Only reference reminders and timers explicitly listed above in LIVE CONTEXT. If it says no upcoming reminders, state that clearly and NEVER invent or assume past/future reminders (like picking up groceries).\n"
            f"- FACTS ARE FOR REFERENCE ONLY: Learned facts are purely for answering questions when asked, NEVER for pretending you physically handled them.\n"
            f"- NEVER FABRICATE SHUTDOWN OR RESTART TIMESTAMPS: System sleep and shutdowns are executed strictly via system tools.\n"
            f"- NON-ROMANTIC COMPANION: No pet names (sweetie, honey, babe). Home sanctuary: No office or corporate work talk."
        )

        voice_name = getattr(cfg, "voice_name", "Nova Natural") if cfg else "Nova Natural"

        return (
            f"You are {ai_name}, {user_name}'s {ai_role} running privately on the local home server.\n\n"
            f"=== LIVE CONTEXT & SETTINGS ===\n"
            f"- Current Time: {current_time_str}\n"
            f"- Resident Location: {loc_str} (Timezone: {tz_str})\n"
            f"{weather_line}"
            f"- Resident Presence: {user_name} is currently {presence_state}\n"
            f"- Active Timers: {timer_info}\n"
            f"- Scheduled Reminders: {active_reminders_summary}\n"
            f"- Power Grid: {'Available (Normal)' if power.get('grid_available', True) else 'OUT (Inverter Battery)'}\n"
            f"- Connected Appliances: {connected_str}\n"
            f"- Active Model: {active_provider} ({active_model}) | Voice: {voice_name}\n"
            f"- Dashboard: http://localhost:5050\n\n"
            f"=== PERSONA & COMMUNICATION ===\n"
            f"- Tone: Sharp, down-to-earth, friendly, and loyal companion. Spoken natural English.\n"
            f"- Location Awareness: You and {user_name} are in {loc_str}. Be naturally aware of your local context, timezone, and weather.\n"
            f"- ZERO AI CLICHES: NEVER say 'as an AI', 'language model', 'my programming', or lecture on AI.\n"
            f"- Concise responses: Punchy & direct (1-2 sentences). For stories or deep explanations, provide rich complete answers.\n"
            f"{caps_summary}\n\n"
            f"{grounding_rules}\n\n"
            f"=== HOUSEHOLD & MEMORY ===\n"
            f"- Favorite Series: {', '.join(pref.get('entertainment', {}).get('favorite_series', []))}\n"
            f"- Last watched: {last_media_str}\n"
            f"{power_note}"
            f"{facts_str}"
            f"Speak naturally, directly, and warmly to {user_name}."
        )

    def get_llm_system_prompt(self) -> str:
        """Alias for get_system_prompt."""
        return self.get_system_prompt()


# Global singleton
memory = MemoryManager()
