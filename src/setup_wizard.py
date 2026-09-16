import os
import sys
import time
import webbrowser
import threading
from src.web_server import run_web_server

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def is_first_time_setup():
    """Checks if the project hasn't been configured yet."""
    if not os.path.exists(CONFIG_PATH):
        return True
    try:
        import json
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # If user_name is default/empty, or setup_completed is not True
            if not data.get("user_name") or data.get("setup_completed") is not True:
                return True
    except Exception:
        return True
    return False


def launch_setup_wizard(port=5050, force_browser=True):
    print("\n" + "=" * 60)
    print("  🚀 Smart Home AI Assistant — Setup & Onboarding Wizard")
    print("=" * 60)
    print(f"\n[Setup] Launching local configuration interface on port {port}...")

    server = run_web_server(host="0.0.0.0", port=port, background=True)
    if not server:
        print("[Setup] Failed to start local server. Please check port availability.")
        return

    actual_port = server.server_port
    url = f"http://localhost:{actual_port}/setup"

    print(f"\n✨ Setup Wizard ready!")
    print(f"👉 Please open in your browser: {url}")
    print("\nOpening your default web browser now...")

    if force_browser:
        def _open_url():
            time.sleep(1.0)
            webbrowser.open(url)
        threading.Thread(target=_open_url, daemon=True).start()

    print("\nKeep this terminal window open while completing the setup.")
    print("Press Ctrl+C anytime to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Setup] Setup wizard stopped.")
        sys.exit(0)


if __name__ == "__main__":
    launch_setup_wizard()
