import sys
from src.config import load_config
from src.presence import PresenceTracker
from src.voice_output import speak
from src.voice_input import VoiceListener

def test_config():
    print("Testing config loading...")
    config = load_config()
    assert config.user_name == "Timilehin", f"Expected Timilehin, got {config.user_name}"
    print(f"✅ Config passed: User={config.user_name}, Phone IP={config.phone_ip}")

def test_presence():
    print("\nTesting presence detection on localhost (127.0.0.1)...")
    tracker = PresenceTracker("127.0.0.1")
    is_online = tracker.ping_once()
    assert is_online is True, "Localhost ping should succeed"
    print("✅ Presence check passed: 127.0.0.1 is online")

def test_voice_output():
    print("\nTesting voice output...")
    speak("Home AI Assistant voice output is functional.")
    print("✅ Voice output completed")

def test_voice_input_init():
    print("\nTesting microphone / voice listener initialization...")
    listener = VoiceListener()
    if listener.available:
        print("✅ Voice listener initialized with microphone available.")
    else:
        print("⚠️ Voice listener initialized in fallback mode (microphone unavailable or permissions needed).")

def test_memory():
    print("\nTesting memory manager...")
    from src.memory import memory
    prompt = memory.get_llm_system_prompt()
    assert "Timilehin" in prompt, "Prompt should contain user name Timilehin"
    assert "Merlin" in prompt, "Prompt should contain favorite series Merlin"
    print("✅ Memory manager loaded and generated valid LLM system prompt.")

def test_brain():
    print("\nTesting local LLM brain...")
    from src.brain import brain
    if brain.available:
        reply = brain.generate_response("Hello, I am home.")
        print(f"✅ Local Brain generated response: \"{reply}\"")
    else:
        print("⚠️ Local Brain using rule-based fallback.")

if __name__ == "__main__":
    print("=== Running Home AI Assistant Component Tests ===")
    test_config()
    test_presence()
    test_voice_output()
    test_voice_input_init()
    test_memory()
    test_brain()
    print("\n🎉 All component tests completed successfully!")
