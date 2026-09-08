import json
import os
from dataclasses import dataclass, field
from typing import List

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


@dataclass
class AppConfig:
    user_name: str = "Timilehin"
    phone_ip: str = "192.168.1.150"
    presence_poll_interval_seconds: int = 5
    presence_debounce_count: int = 2
    greeting_text: str = "Welcome home, Timilehin. How was your day?"
    trigger_phrases: List[str] = field(default_factory=lambda: ["hello", "hey", "hi"])
    voice_name: str = "default"
    listen_timeout_seconds: int = 7
    phrase_time_limit_seconds: int = 5


def load_config(path: str = CONFIG_FILE_PATH) -> AppConfig:
    """Loads configuration from JSON file, falling back to defaults for missing fields."""
    if not os.path.exists(path):
        return AppConfig()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppConfig(
            user_name=data.get("user_name", "Timilehin"),
            phone_ip=data.get("phone_ip", "192.168.1.150"),
            presence_poll_interval_seconds=int(data.get("presence_poll_interval_seconds", 5)),
            presence_debounce_count=int(data.get("presence_debounce_count", 2)),
            greeting_text=data.get("greeting_text", "Welcome home, Timilehin. How was your day?"),
            trigger_phrases=data.get("trigger_phrases", ["hello", "hey", "hi"]),
            voice_name=data.get("voice_name", "default"),
            listen_timeout_seconds=int(data.get("listen_timeout_seconds", 7)),
            phrase_time_limit_seconds=int(data.get("phrase_time_limit_seconds", 5)),
        )
    except Exception as e:
        print(f"Warning: Failed to parse config file ({e}). Using defaults.")
        return AppConfig()
