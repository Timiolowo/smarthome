#!/usr/bin/env python3
"""
Terminal Voice Showcase — Sample all installed macOS voices through your speakers!
Usage: python3 test_terminal_voices.py
"""
import subprocess
import time
import sys

VOICES = [
    ("Samantha", "Hello Timilehin, this is Samantha. Welcome home, how was your day?"),
    ("Karen", "G'day Timilehin, this is Karen. How can I assist you today?"),
    ("Flo (English (US))", "Hi Timilehin, this is Flo speaking. Ready for your commands."),
    ("Daniel (English (UK))", "Good day Timilehin, this is Daniel. Everything in your home is running smoothly."),
    ("Moira (English (Ireland))", "Hello Timilehin, this is Moira. The weather is lovely today."),
    ("Tessa", "Hello Timilehin, this is Tessa. What would you like to listen to?"),
    ("Shelley (English (US))", "Hi Timilehin, this is Shelley. Let me know if you need anything."),
    ("Eddy (English (US))", "Hey Timilehin, this is Eddy. All systems are online.")
]

def main():
    print("=" * 65)
    print("       🎙️ macOS Terminal Voice Comparison Showcase")
    print("=" * 65)
    print("Listen to each voice playing through your Mac speakers...\n")

    for name, sample in VOICES:
        print(f"▶️ Playing: [{name}]")
        print(f"   \"{sample}\"\n")
        try:
            subprocess.run(["say", "-v", name, sample])
        except Exception as e:
            print(f"   Error playing {name}: {e}")
        time.sleep(0.5)

    print("=" * 65)
    print("✨ Comparison complete! Which voice did you like best?")
    print("To set any of these as your default assistant voice, tell me its name.")
    print("=" * 65)

if __name__ == "__main__":
    main()
