"""Cross-platform reporting for voice interruption support."""

import platform


def interruption_capabilities(echo_cancelled: bool) -> dict:
    """Describe controls that are safe for the active audio backend."""
    return {
        "platform": platform.system().lower(),
        "provider_stream": True,
        "web_ui": True,
        "keyboard": True,
        "voice_barge_in": bool(echo_cancelled),
    }
