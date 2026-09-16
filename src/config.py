import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Union

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
    conversation_timeout_seconds: int = 30
    conversation_phrase_limit_seconds: int = 25
    microphone_device: Optional[Union[int, str]] = None
    echo_cancellation: bool = True
    ready_chime: bool = False
    llm_provider: str = "local"
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None


def load_config(path: str = CONFIG_FILE_PATH) -> AppConfig:
    """Loads configuration from JSON file, falling back to defaults for missing fields."""
    if not os.path.exists(path):
        return AppConfig()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Provider fallback compatibility: check llm_provider first, then legacy ai_mode/cloud_provider
        provider = data.get("llm_provider")
        if not provider and data.get("ai_mode") == "cloud":
            provider = data.get("cloud_provider", "openai")
        provider = provider or "local"

        api_key = data.get("llm_api_key") or data.get("cloud_api_key")

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
            conversation_timeout_seconds=max(5, min(300, int(data.get("conversation_timeout_seconds", 30)))),
            conversation_phrase_limit_seconds=max(5, min(60, int(data.get("conversation_phrase_limit_seconds", 25)))),
            microphone_device=data.get("microphone_device"),
            echo_cancellation=data.get("echo_cancellation", True) is True,
            ready_chime=data.get("ready_chime", False) is True,
            llm_provider=provider,
            llm_model=data.get("llm_model"),
            llm_api_key=api_key,
            llm_base_url=data.get("llm_base_url"),
        )
    except Exception as e:
        print(f"Warning: Failed to parse config file ({e}). Using defaults.")
        return AppConfig()
