import argparse
import sys
import time

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    class DummyColor:
        def __getattr__(self, name):
            return ""
    Fore = DummyColor()
    Style = DummyColor()

from src.config import load_config
from src.agent import agent
from src.brain import brain
from src.memory import memory
from src.presence import PresenceTracker
from src.voice_input import VoiceListener
from src.voice_output import speak
from src.web_server import run_web_server

EXIT_PHRASES = [
    "that's all",
    "thats all",
    "goodnight",
    "good night",
    "bye",
    "goodbye",
    "stop",
    "i'm good",
    "im good",
    "nothing else",
    "never mind",
    "nevermind",
]

WAKE_TRIGGERS = ["hey", "hello", "hi", "assistant", "timilehin"]


def run_assistant(simulate_presence: bool = False):
    config = load_config()

    print(f"\n{Fore.CYAN}{Style.BRIGHT}================================================")
    print(f"       🏡  TIMILEHIN HOME AI ASSISTANT         ")
    print(f"================================================{Style.RESET_ALL}")
    print(f"User:             {Fore.GREEN}{config.user_name}{Style.RESET_ALL}")
    print(f"Target Phone IP:  {Fore.YELLOW}{config.phone_ip}{Style.RESET_ALL}")
    print(f"Trigger Phrases:  {Fore.YELLOW}{', '.join(config.trigger_phrases)}{Style.RESET_ALL}")
    print(f"Offline Brain:    {Fore.GREEN if brain.available else Fore.RED}{'Llama 3.2 1B Active' if brain.available else 'Rule-based Fallback'}{Style.RESET_ALL}")
    print(f"Simulate Home:    {simulate_presence}")
    print(f"{Fore.CYAN}================================================\n{Style.RESET_ALL}")

    tracker = PresenceTracker(
        target_ip=config.phone_ip,
        debounce_count=config.presence_debounce_count,
    )

    # Start local web configuration server in background
    run_web_server(host="0.0.0.0", port=5050, background=True)

    listener = VoiceListener()
    listener.calibrate()

    # States: AWAY -> WAITING_FOR_HELLO -> CONVERSING <-> HOME_STANDBY
    state = "AWAY"

    print(f"{Fore.BLUE}ℹ️  Assistant running. Monitoring arrival for {config.user_name}...{Style.RESET_ALL}\n")

    try:
        while True:
            if simulate_presence:
                is_home = True
            else:
                is_home = tracker.update()

            # -------------------------------------------------------------
            # STATE 1: AWAY (Waiting for phone to appear on Wi-Fi)
            # -------------------------------------------------------------
            if state == "AWAY":
                if is_home:
                    memory.update_presence(True)
                    print(f"\n{Fore.GREEN}📍 [PRESENCE]: {config.user_name}'s phone detected on home network!{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}👂 [VOICE]: Waiting for {config.user_name} to say hello...{Style.RESET_ALL}")
                    state = "WAITING_FOR_HELLO"
                else:
                    print(f"⏳ [AWAY]: {config.user_name} is away. Checking again in {config.presence_poll_interval_seconds}s...", end="\r", flush=True)
                    time.sleep(config.presence_poll_interval_seconds)

            # -------------------------------------------------------------
            # STATE 2: WAITING_FOR_HELLO (Detected arrival, awaiting first greeting)
            # -------------------------------------------------------------
            elif state == "WAITING_FOR_HELLO":
                heard_greeting = listener.wait_for_trigger(
                    triggers=config.trigger_phrases,
                    timeout=config.listen_timeout_seconds,
                    phrase_time_limit=config.phrase_time_limit_seconds,
                )

                if heard_greeting:
                    print(f"\n{Fore.GREEN}✨ [TRIGGER]: Greeting acknowledged!{Style.RESET_ALL}")
                    if brain.available:
                        greeting = brain.generate_response("Hello, I just arrived home.")
                    else:
                        greeting = config.greeting_text

                    speak(greeting, listener=listener, interruptible=False, voice=config.voice_name)
                    # Enter continuous dialogue mode immediately!
                    state = "CONVERSING"
                else:
                    # Check if user left while waiting
                    if not simulate_presence and not tracker.update():
                        memory.update_presence(False)
                        print(f"\n{Fore.YELLOW}📍 [PRESENCE]: Device disconnected. Returning to AWAY state.{Style.RESET_ALL}")
                        state = "AWAY"

            # -------------------------------------------------------------
            # STATE 3: CONVERSING (Interactive multi-turn continuous dialogue)
            # -------------------------------------------------------------
            elif state == "CONVERSING":
                user_said = listener.listen_once(
                    timeout=8,
                    phrase_time_limit=10,
                )

                if user_said:
                    # Check if user wants to close the conversation
                    if any(exit_word in user_said for exit_word in EXIT_PHRASES):
                        print(f"\n{Fore.CYAN}👋 [CONVERSATION ENDED]: Closing dialogue loop.{Style.RESET_ALL}")
                        farewell = "Enjoy your evening, Timilehin. Let me know if you need anything."
                        speak(farewell, interruptible=False, voice=config.voice_name)
                        state = "HOME_STANDBY"
                        print(f"\n{Fore.BLUE}💤 [STANDBY]: System in standby. Say 'Hey' or 'Hello' anytime to talk.{Style.RESET_ALL}\n")
                    else:
                        # Multi-turn response with agentic tool routing and memory
                        reply = agent.process_message(user_said)
                        speak(reply, listener=listener, interruptible=False, voice=config.voice_name)
                        # Loop remains in CONVERSING for next turn
                else:
                    # User stopped talking / silence timeout -> transition to standby
                    state = "HOME_STANDBY"
                    print(f"\n{Fore.BLUE}💤 [STANDBY]: Conversation paused. Say 'Hey' or 'Hello' anytime to resume.{Style.RESET_ALL}\n")

            # -------------------------------------------------------------
            # STATE 4: HOME_STANDBY (Quietly waiting for wake word or departure)
            # -------------------------------------------------------------
            elif state == "HOME_STANDBY":
                if not simulate_presence and not tracker.update():
                    memory.update_presence(False)
                    print(f"\n{Fore.RED}📍 [PRESENCE]: {config.user_name} departed (phone disconnected).{Style.RESET_ALL}")
                    state = "AWAY"
                else:
                    # Listen briefly for wake words (e.g. "hey", "hello")
                    woke_up = listener.wait_for_trigger(
                        triggers=WAKE_TRIGGERS,
                        timeout=4,
                        phrase_time_limit=4,
                    )
                    if woke_up:
                        print(f"\n{Fore.GREEN}✨ [WAKE TRIGGER]: Assistant activated!{Style.RESET_ALL}")
                        speak("Yes, Timilehin?", listener=listener, interruptible=False, voice=config.voice_name)
                        state = "CONVERSING"

    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Shutting down Home Assistant. Goodbye!{Style.RESET_ALL}")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Timilehin Home AI Assistant")
    parser.add_argument(
        "--simulate-presence",
        action="store_true",
        help="Simulate that the user is immediately home (skips Wi-Fi ping check for testing voice)",
    )
    parser.add_argument(
        "--web-only",
        action="store_true",
        help="Run only the local web dashboard without microphone/voice listening",
    )
    args = parser.parse_args()

    if args.web_only:
        run_web_server(host="0.0.0.0", port=5050, background=False)
        return

    run_assistant(simulate_presence=args.simulate_presence)


if __name__ == "__main__":
    main()
