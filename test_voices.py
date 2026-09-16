#!/usr/bin/env python3
"""
SmartHome Assistant — Voice & Audio Testing Studio
Tests all available sweet natural voices across both Python offline engines and the browser.
Usage: python3 test_voices.py or ./test_voices.py
"""
import os
import sys
import time
import webbrowser
import platform
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(SCRIPT_DIR, ".venv", "bin", "python")

if os.path.exists(VENV_PYTHON) and sys.executable != VENV_PYTHON:
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

sys.path.insert(0, SCRIPT_DIR)

from src.voice_output import speak, Speaker
from src.web_server import run_web_server

def test_python_voices():
    print("=" * 60)
    print("       🎵 SmartHome Assistant — Voice Testing Studio")
    print("=" * 60)
    
    test_phrase = "Welcome home, Timilehin! How was your day?"
    print(f"\nTesting phrase: \"{test_phrase}\"\n")

    # 1. Test macOS / System Voice
    print("1. Playing macOS / System Voice...")
    speak(test_phrase)
    time.sleep(1.0)

    # 2. Launch Local Voice Studio in Browser
    print("\n2. Launching Interactive Sweet Voice Studio in your browser...")
    server = run_web_server(host="0.0.0.0", port=5050, background=True)
    if server:
        actual_port = server.server_port
        voice_url = f"http://localhost:{actual_port}/test_voices.html"
        print(f"\n✨ Voice Studio running at: {voice_url}")
        print("Opening your browser to test and preview all natural voices...\n")
        webbrowser.open(voice_url)
        print("Press Ctrl+C anytime to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nVoice studio stopped.")

if __name__ == "__main__":
    test_python_voices()
