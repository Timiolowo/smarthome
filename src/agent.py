import json
import os
import random
import re
from datetime import datetime
from typing import Optional, Tuple

from src.brain import brain
from src.memory import memory
from src.tools import tools

CHAT_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "chat_history.json",
)


class HomeAgent:
    def __init__(self, history_file: str = CHAT_HISTORY_FILE):
        self.history_file = history_file
        self.persistent_history = self._load_chat_history()

    def _load_chat_history(self) -> list:
        """Loads previous conversation turns from disk."""
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_turn(self, role: str, content: str) -> None:
        """Appends a turn to the persistent chat history."""
        self.persistent_history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        })
        # Keep recent 40 turns
        if len(self.persistent_history) > 40:
            self.persistent_history = self.persistent_history[-40:]

        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.persistent_history, f, indent=2)
        except Exception as e:
            print(f"[Agent] Failed to save chat history: {e}")

    def _route_intent_or_tool(self, user_text: str) -> Optional[str]:
        """Checks for tool commands or quick intents. Returns string response if matched, or None."""
        cleaned = user_text.strip().lower()

        # -------------------------------------------------------------
        # TOOL 1A: Change Assistant's Name
        # e.g. "I think I would like to call you Sam, so answer when I call you that"
        # e.g. "I want to call you Jarvis", "Change your name to Friday", "Call yourself TARS"
        # -------------------------------------------------------------
        asst_name_match = re.search(
            r"(?:(?:i\s+(?:think\s+)?(?:i\s+)?(?:would\s+like|want|plan|prefer|am\s+going|wish)\s+to\s+call\s+you)|(?:(?:can\s+(?:i|we)|let(?:'s|\s+us))\s+call\s+you)|(?:call\s+you(?:rself)?)|(?:(?:change|set|switch)\s+(?:your|assistant)\s+name\s+to)|(?:your\s+name\s+is\s+(?:now\s+)?)|(?:from\s+now\s+on\s+(?:your\s+name\s+is|i(?:'ll|\s+will)\s+call\s+you))|(?:i(?:'ll|\s+will)\s+(?:be\s+)?calling\s+you)|(?:i(?:'ll|\s+will)\s+call\s+you))\s+([a-zA-Z]+)",
            cleaned,
            re.IGNORECASE,
        )
        if asst_name_match:
            new_name = asst_name_match.group(1)
            response = tools.update_assistant_name(new_name)
            brain.reset_history()  # Refresh LLM system prompt with new assistant name
            return response

        # -------------------------------------------------------------
        # TOOL 1B: Change User's Preferred Name
        # e.g. "I want you to address me as Sam", "Call me Alex", "My name is Timi"
        # -------------------------------------------------------------
        name_match = re.search(
            r"(?:(?:i\s+(?:want|would\s+like)\s+you\s+to\s+)?address\s+me\s+as|call\s+me|my\s+name\s+is)\s+([a-zA-Z]+)",
            cleaned,
            re.IGNORECASE,
        )
        if name_match:
            new_name = name_match.group(1)
            response = tools.update_preferred_name(new_name)
            brain.reset_history()  # Refresh LLM system prompt with new user name
            return response

        # -------------------------------------------------------------
        # TOOL 1C: Standby / Ambient Sleep Display
        # e.g. "go on standby", "okay, go on standby", "enter standby mode",
        # "put the screen to sleep", "activate standby", "go to sleep"
        # -------------------------------------------------------------
        if re.search(r"\b(?:go\s+(?:on\s+|to\s+)?standby|enter\s+standby|activate\s+standby|switch\s+to\s+standby|standby\s+mode|go\s+to\s+sleep|sleep\s+mode|put\s+(?:the\s+)?(?:screen|display|system)?\s*(?:to\s+sleep|on\s+standby))\b", cleaned):
            return "Going into ambient standby mode now. Sleeping display."

        # -------------------------------------------------------------
        # TOOL 2: Reminders Engine (Scheduling, Query, Cancellation)
        # e.g. "Remind me in 30 minutes to call mom", "Remind me tomorrow at 9 am to buy coffee"
        # -------------------------------------------------------------
        if re.search(r"\b(what are my reminders|any reminders|check reminders|show reminders|upcoming reminders|list reminders)\b", cleaned):
            return tools.get_active_reminders_summary()

        if re.search(r"\b(cancel (?:all |the |my )?reminders?|clear (?:all |the |my )?reminders?|stop (?:all |the |my )?reminders?)\b", cleaned):
            count = tools.cancel_all_reminders()
            return "I've canceled your upcoming reminders." if count > 0 else "You don't have any active reminders to cancel."

        if cleaned.startswith("remind") or re.search(r"\bremind me\b", cleaned):
            rem_res = tools.parse_and_set_reminder(user_text)
            if rem_res:
                return rem_res

        # -------------------------------------------------------------
        # TOOL 3: Store Facts & Item Locations
        # e.g. "I kept my pen in the top desk drawer", "Remember that my phone password is 1234"
        # -------------------------------------------------------------
        loc_match = re.search(
            r"^(?:i\s+(?:kept|put|left|placed|stored)\s+my\s+([a-zA-Z0-9_\s]+?)\s+(?:in|on|at|under|near|inside)\s+(.+)|my\s+([a-zA-Z0-9_\s]+?\s+(?:password|passcode|pin|code|key))\s+is\s+(.+))",
            cleaned,
            re.IGNORECASE,
        )
        if loc_match:
            clean_fact = user_text.strip().rstrip(".!?")
            response = tools.remember_fact(clean_fact)
            brain.reset_history()
            return response

        remember_match = re.search(
            r"(?:remember that|remember this\s*[:-]?|you need to remember that|you need to remember|save this fact\s*[:-]?|don't forget that|dont forget that)\s+(.*)",
            user_text,
            re.IGNORECASE,
        )
        if remember_match:
            fact_content = remember_match.group(1).strip()
            fact_content = re.sub(r"[.!?]+$", "", fact_content)
            response = tools.remember_fact(fact_content)
            brain.reset_history()  # Refresh LLM with new learned fact
            return response

        # -------------------------------------------------------------
        # TOOL 4: Natural Fact Recall ("Where did I put my pen?", "What is my phone password?")
        # -------------------------------------------------------------
        if re.search(r"\b(where (?:did i|is my|are my)|what is my (?:phone |gate |door |wifi |email )?(?:password|passcode|pin|code|key|best food)|what did i tell you about)\b", cleaned):
            found_fact = tools.search_facts(cleaned)
            if found_fact:
                return found_fact

        # -------------------------------------------------------------
        # TOOL 5: Set Timer / Alarm with Sound
        # e.g. "Play an alarm sound in 20 minutes", "Set alarm for 10 seconds", "Set timer for two minutes"
        # -------------------------------------------------------------
        # 5a. Relative duration (seconds / minutes / hours / words)
        if re.search(r"\b(?:play (?:an? )?alarm|set (?:an? )?alarm|ring (?:my )?alarm|set (?:a )?timer|alarm in|timer for|wake me up in)\b", cleaned):
            from src.duration_parser import extract_duration_seconds
            dur = extract_duration_seconds(cleaned)
            if dur is not None and dur > 0:
                label = "alarm" if ("alarm" in cleaned or "wake" in cleaned) else "timer"
                return tools.set_timer(dur, label=label)

        # 5b. Clock time alarm (e.g. "at 7:30 am", "for 8 pm")
        clock_match = re.search(
            r"(?:set (?:an? )?alarm (?:for|at)|alarm (?:at|for)|wake me up (?:at|for))\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})",
            cleaned,
            re.IGNORECASE,
        )
        if clock_match:
            time_str = clock_match.group(1).strip()
            return tools.set_clock_alarm(time_str, label="alarm")

        # -------------------------------------------------------------
        # TOOL 6: Query Active Timers
        # e.g. "How much time is left?", "Any timers running?", "Check timers"
        # -------------------------------------------------------------
        if re.search(r"\b(how much time is left|active timers?|any timers?|check timers?|status of (?:the )?timer|what timer|timers? running)\b", cleaned):
            active = tools.get_active_timers()
            if not active:
                return "You don't have any active timers running right now."
            elif len(active) == 1:
                t = active[0]
                rem_mins = int(t['remaining_seconds'] // 60)
                rem_secs = int(t['remaining_seconds'] % 60)
                time_str = f"{rem_mins}m {rem_secs}s" if rem_mins > 0 else f"{rem_secs}s"
                return f"You have 1 active {t['label']} ({t['display_time']}) with {time_str} remaining."
            else:
                details = []
                for t in active:
                    rem_mins = int(t['remaining_seconds'] // 60)
                    rem_secs = int(t['remaining_seconds'] % 60)
                    time_str = f"{rem_mins}m {rem_secs}s" if rem_mins > 0 else f"{rem_secs}s"
                    details.append(f"{t['label']} ({t['display_time']}, {time_str} left)")
                return f"You have {len(active)} active timers: {', '.join(details)}."

        # -------------------------------------------------------------
        # TOOL 5: Cancel Timers / Alarms
        # e.g. "Cancel timer", "Stop the alarm", "Clear timers"
        # -------------------------------------------------------------
        if re.search(r"\b(cancel (?:the |all )?timers?|stop (?:the |all )?timers?|clear (?:the |all )?timers?|cancel (?:the |all )?alarms?|stop (?:the |all )?alarms?)\b", cleaned):
            count = tools.cancel_all_timers()
            return "I've canceled your active timers." if count > 0 else "There are no active timers to cancel."

        # -------------------------------------------------------------
        # TOOL 6: "What do you know about me?"
        # -------------------------------------------------------------
        if re.search(r"\b(what do you know about me|what do you remember about me|who am i|tell me about me|what shows do i like|what do i like to watch)\b", cleaned):
            mem_data = memory.load_memory()
            name = mem_data.get("profile", {}).get("preferred_name", "Timilehin")
            series = mem_data.get("preferences", {}).get("entertainment", {}).get("favorite_series", [])
            facts = mem_data.get("learned_facts", [])

            summary = f"You are {name}. You love high-concept sci-fi and fantasy shows like {', '.join(series)}."
            if facts:
                summary += f" I also remember: {'; '.join(facts[-3:])}."
            return summary

        # -------------------------------------------------------------
        # TOOL 7: "Who are you?" / About the AI
        # -------------------------------------------------------------
        if re.search(r"\b(who are you|what are you|tell me about yourself|what is your name)\b", cleaned):
            asst_data = memory.load_assistant()
            name = asst_data.get("name", "Nova")
            provider_desc = f"{brain.provider_name} ({brain.model_name})" if brain.available else "local offline brain"
            return f"I am {name}, your private local smart home assistant running on your home server with a {provider_desc}. All your data stays 100% private."

        # -------------------------------------------------------------
        # TOOL 8: App Capabilities ("what can you do", "capabilities", "features")
        # -------------------------------------------------------------
        if re.search(r"\b(what can you do|what are your capabilities|what are your features|what do you do|help me|how can you help|what can i ask you)\b", cleaned):
            asst_data = memory.load_assistant()
            name = asst_data.get("name", "Nova")
            return (
                f"I'm {name}. I can set relative timers (e.g. 'timer for 15 minutes'), set clock alarms (e.g. 'alarm for 7:30 AM'), "
                f"check active timers, remember facts you tell me ('remember that...'), welcome you home automatically when your phone connects, "
                f"and chat. You can also manage everything on the web dashboard at localhost:5050."
            )

        # -------------------------------------------------------------
        # TOOL 9: App Limits ("what are your limits", "what can't you do")
        # -------------------------------------------------------------
        if re.search(r"\b(what are your limits|what can'?t you do|what are your limitations|your limits|what are you not able to do)\b", cleaned):
            return (
                "I have no physical body, so I can't fetch drinks, cook, or move objects. "
                "I don't have smart lights, AC, or TV switches connected yet, and I keep home as a sanctuary with zero corporate or office work talk."
            )

        # -------------------------------------------------------------
        # TOOL 10: How It Works / How to Use
        # -------------------------------------------------------------
        if re.search(r"\b(how do you work|how do i use (this|you|the app)|how does (this|the app) work|how to use you)\b", cleaned):
            asst_data = memory.load_assistant()
            name = asst_data.get("name", "Nova")
            return (
                f"Just say '{name}' or 'Hey' to wake me. Once we start talking, I stay listening for follow-ups so you don't have to repeat my name. "
                f"You can interrupt me mid-sentence anytime by speaking. Say 'That's all' or 'Goodnight' when you're done, or visit localhost:5050 for the dashboard."
            )

        # -------------------------------------------------------------
        # TOOL 11: Connected Device Queries (Lights, AC, TV) - Grounded
        # -------------------------------------------------------------
        dev_ctrl_match = re.search(
            r"\b(turn on|turn off|switch on|switch off|toggle)\s+(?:the\s+)?(lights?|ac|air condition(?:er|ing)?|tv|television|fans?|plugs?)\b",
            cleaned,
            re.IGNORECASE,
        )
        if dev_ctrl_match:
            action = dev_ctrl_match.group(1).lower()
            device_type = dev_ctrl_match.group(2).lower()
            if "light" in device_type:
                return tools.control_lights(action)
            elif "ac" in device_type or "air" in device_type:
                return tools.control_ac(action)
            elif "tv" in device_type or "television" in device_type:
                return tools.control_tv(action)
            else:
                from src.device_inventory import device_inventory
                return device_inventory.get_grounded_refusal(device_type, action)

        # -------------------------------------------------------------
        # TOOL 12: Real-Time Clock & Date Query
        # e.g. "What is the time?", "What time is it?", "What's today's date?", "What day is it?"
        # -------------------------------------------------------------
        if re.search(r"\b(what('s| is) the time|what time is it|tell me the time|current time|what('s| is) (the |today's )?date|what day is it( today)?|what is today's date)\b", cleaned):
            now = datetime.now()
            time_display = now.strftime("%I:%M %p").lstrip("0")
            date_display = now.strftime("%A, %B %d")
            return f"It is {time_display} on {date_display}."

        # -------------------------------------------------------------
        # TOOL 12b: Live Weather & Location Awareness
        # e.g. "what's the weather", "how's the weather outside", "where am I", "what is my location"
        # -------------------------------------------------------------
        if re.search(r"\b(what('s| is) the weather|weather report|weather forecast|how('s| is) the weather|temperature outside|what('s| is) (my|our) location|where am i|what city am i in)\b", cleaned):
            return tools.get_weather_and_location()

        # -------------------------------------------------------------
        # TOOL 13: Timed Sleep & Automated Return / Immediate Power Off
        # e.g. "shut down and come online in 5 minutes", "shut down for 10 minutes", "show down your system or combat online in five minutes", "power off"
        # -------------------------------------------------------------
        sleep_cmd_match = re.search(
            r"\b(?:turn (?:yourself )?off|turn off|shut down|show down|shot that|power off|power down|go to sleep|take a nap|sleep|rest|come back|come online|combat online|return)\b",
            cleaned
        )
        follow_up_duration = re.search(
            r"\b(?:i said|make it|wait for|come back in|come online in|combat online in|return in|for|in)\s+(?:about\s+|around\s+|the\s+next\s+)?[a-zA-Z0-9_.\s-]+\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?)\b",
            cleaned
        )

        if sleep_cmd_match or follow_up_duration:
            from src.duration_parser import extract_duration_seconds
            dur = extract_duration_seconds(cleaned)
            if dur is not None and dur > 0:
                return tools.schedule_sleep_and_return(dur)
            # If user explicitly said shut down / power off / turn off without a duration:
            if sleep_cmd_match and not any(w in cleaned for w in ("light", "ac", "tv", "fan", "plug", "3d", "2d", "theme", "kiosk", "screen", "visualizer", "orb", "core", "tab")):
                from src.system_power import system_power
                system_power.power_off()
                return "I'm powering off now. You can turn me back on from the dashboard or by restarting."

        # -------------------------------------------------------------
        # TOOL 14: System Health, Wi-Fi & Battery Awareness
        # -------------------------------------------------------------
        if re.search(r"\b(what('s| is) (our|the|my) wi-?fi( status)?|check wi-?fi|wi-?fi status|is wi-?fi connected|wi-?fi info)\b", cleaned):
            return tools.get_wifi_info()

        if re.search(r"\b(check system( health| status| stats)?|system health|system status|how is the system|how is the server|battery (status|level|percent|health)|check battery)\b", cleaned):
            return tools.get_system_health()

        # -------------------------------------------------------------
        # TOOL 15: Android Phone Status & Outbound Phone Calls (ADB Bridge)
        # e.g. "Call Mom", "Dial 555-0199", "Check phone status"
        # -------------------------------------------------------------
        call_match = re.search(
            r"^(?:please\s+)?(?:call|dial|phone)\s+([a-zA-Z0-9_+*#-]+(?:\s+[a-zA-Z0-9_+*#-]+)*)$",
            cleaned,
            re.IGNORECASE,
        )
        if call_match and not any(w in cleaned for w in ("routine", "theme", "yourself", "alarm", "timer")):
            target = call_match.group(1).strip()
            return tools.make_phone_call(target)

        if re.search(r"\b(phone status|check (?:my )?phone|is (?:my )?phone connected|android status)\b", cleaned):
            return tools.get_phone_status()

        # -------------------------------------------------------------
        # TOOL 16: Smart-Home Routines ("Good morning routine", "Bedtime", "Focus mode")
        # -------------------------------------------------------------
        routine_match = re.search(
            r"\b(?:run|start|trigger|execute)\s+(?:the\s+)?(good morning|bedtime|goodnight|focus(?: mode)?|movie(?: time)?)\s*(?:routine|mode)?\b",
            cleaned,
            re.IGNORECASE,
        )
        if routine_match:
            r_name = routine_match.group(1).strip()
            return tools.trigger_routine(r_name)

        if re.search(r"\b(good morning routine|bedtime routine|start focus session|movie mode)\b", cleaned):
            return tools.trigger_routine(cleaned)

        # -------------------------------------------------------------
        # TOOL 17A: Visual Engine Switching (3D Particle Orb vs 2D Core)
        # e.g. "can you put it in 3d", "let's see the 3d orb", "turn off 3d", "switch back to 2d"
        # -------------------------------------------------------------
        is_3d_mention = bool(re.search(r"\b(3d|three d|particle orb|particles? orb|3-d)\b", cleaned))
        is_2d_mention = bool(re.search(r"\b(2d|two d|reactor core|concentric|2-d)\b", cleaned))
        is_disable_3d = bool(re.search(r"\b(turn off 3d|disable 3d|exit 3d|no 3d|back to 2d|switch back to 2d|leave 3d)\b", cleaned))

        if is_disable_3d:
            return tools.set_visual_engine("2d")
        elif is_3d_mention and not any(w in cleaned for w in ("movie", "glasses", "printer")):
            return tools.set_visual_engine("3d")
        elif is_2d_mention:
            return tools.set_visual_engine("2d")

        # -------------------------------------------------------------
        # TOOL 17B: Dashboard Tab Navigation
        # e.g. "pull up the settings page", "take me to alarms", "let's look at the overview", "show my profile"
        # -------------------------------------------------------------
        tab_nav_match = re.search(
            r"\b(?:switch to|show|open|go to|navigate to|pull up|take me to|bring up|let'?s see|let'?s look at|head to|display)\s+(?:me\s+)?(?:my\s+)?(?:the\s+)?(?:dashboard\s+)?(overview|status|dossier|profile|alarms?|timers?|settings?|config(?:uration)?|chat|console|architecture|live\s*display|display)\s*(?:tab|page|screen|view)?\b",
            cleaned,
            re.IGNORECASE,
        )
        if tab_nav_match and not any(w in cleaned for w in ("camera", "door", "gate", "light")):
            target_tab = tab_nav_match.group(1).strip()
            return tools.switch_dashboard_tab(target_tab)

        # -------------------------------------------------------------
        # TOOL 17C: Fullscreen Kiosk Mode
        # e.g. "enter kiosk mode", "put this in fullscreen", "exit kiosk mode"
        # -------------------------------------------------------------
        if re.search(r"\b(enter (?:fullscreen|kiosk)(?: mode)?|fullscreen (?:dashboard|mode)?|put this in (?:fullscreen|kiosk)|kiosk mode on)\b", cleaned):
            return tools.set_kiosk_mode(True)
        if re.search(r"\b(exit (?:fullscreen|kiosk)(?: mode)?|leave (?:fullscreen|kiosk)(?: mode)?|kiosk mode off)\b", cleaned):
            return tools.set_kiosk_mode(False)

        # -------------------------------------------------------------
        # TOOL 17D: UI Theme & Color Switching
        # e.g. "make the dashboard green", "turn on dark mode", "give me the cyberpunk look", "switch to amber"
        # -------------------------------------------------------------
        color_theme_map = {
            "emerald": "emerald", "green": "emerald",
            "cyberpunk": "cyberpunk", "neon": "cyberpunk",
            "midnight": "midnight", "dark": "midnight", "black": "midnight",
            "light": "light", "white": "light",
            "amber": "amber", "orange": "amber", "yellow": "amber",
            "nord": "nord", "blue": "nord",
        }
        for k_color, v_theme in color_theme_map.items():
            if re.search(rf"\b(?:theme|color|mode|look)\s+(?:to\s+|is\s+)?{k_color}\b", cleaned) or \
               re.search(rf"\b(?:switch to|change to|make it|make the dashboard|make the screen|set to|turn on)\s+(?:the\s+)?{k_color}(?:\s+theme|\s+mode|\s+color|\s+look)?\b", cleaned):
                return tools.set_ui_theme(v_theme)

        # -------------------------------------------------------------
        # TOOL 18: Reversible Undo Stack ("Undo that", "Undo last action")
        # -------------------------------------------------------------
        if re.search(r"\b(undo that|undo last action|undo it|revert that|undo)\b", cleaned):
            return tools.undo_last_action()

        # -------------------------------------------------------------
        # TOOL 19: Live Active Settings Query
        # e.g. "What are my settings?", "What model are you running?", "Check settings"
        # -------------------------------------------------------------
        if re.search(r"\b(what are my settings|what settings (do i have|are on)|check settings|show (my )?settings|what model are you running|what model is (this|active)|what voice are you using)\b", cleaned):
            from src.config import load_config
            cfg = load_config()
            active_timers = tools.get_active_timers()
            timer_summary = f"{len(active_timers)} active timer(s)" if active_timers else "No active timers"
            return (
                f"Here are your active settings: Brain model is {brain.provider_name} ({brain.model_name}), "
                f"voice is {cfg.voice_name}, echo cancellation is {'enabled' if cfg.echo_cancellation else 'disabled'}, "
                f"conversation timeout is {cfg.conversation_timeout_seconds}s, and phone tracking IP is {cfg.phone_ip}. "
                f"Status: {timer_summary}."
            )

        # -------------------------------------------------------------
        # TOOL 20: Greeting / Wellness Check ("how are you", "how's it going")
        # -------------------------------------------------------------
        if re.search(r"\b(how are you|how('s| is) it going|how('s| is) your day|how('s| are) you doing|how do you feel|you good|you alright|are you okay|what's good)\b", cleaned):
            mem_data = memory.load_memory()
            user_name = mem_data.get("profile", {}).get("preferred_name", "Timilehin")
            responses = [
                f"Doing great, {user_name}! Always good to chat with you. What's on your mind?",
                "I'm feeling sharp! What can I help with?",
                f"All good on my end! How about you, {user_name} — how's everything going?",
                "Couldn't be better! What are we getting into?",
                f"I'm here and ready! Good to see you, {user_name}. What do you need?",
            ]
            return random.choice(responses)

        return None

    def process_message(self, user_text: str) -> str:
        """
        Agentic Intent Router with Compound Command Execution:
        1. Checks for direct single-turn tool commands.
        2. If not matched, decomposes compound multi-intent sentences if present.
        3. Falls back to LLM conversation with persistent context.
        """
        self._save_turn("user", user_text)
        tool_reply = self._route_intent_or_tool(user_text)
        if tool_reply is not None:
            self._save_turn("assistant", tool_reply)
            return tool_reply

        from src.routines import routine_engine
        sub_commands = routine_engine.decompose_compound_command(user_text)
        if len(sub_commands) > 1:
            replies = []
            for sub_cmd in sub_commands:
                # Use sub_route or process without re-saving the top user turn
                sub_tool = self._route_intent_or_tool(sub_cmd)
                if sub_tool is not None:
                    replies.append(sub_tool)
                else:
                    replies.append(brain.chat(sub_cmd))
            combined = " ".join(replies)
            self._save_turn("assistant", combined)
            return combined

        reply = brain.chat(user_text)
        self._save_turn("assistant", reply)
        return reply

    def process_message_stream(self, user_text: str, cancel_event=None):
        """
        Streaming Intent Router with Compound Command Execution:
        - If direct tool/intent matched: yields the single complete response.
        - If compound: yields sequentially executed sub-command results.
        - If casual conversation: yields sentence stream from LLM brain.
        """
        self._save_turn("user", user_text)
        tool_reply = self._route_intent_or_tool(user_text)
        if tool_reply is not None:
            self._save_turn("assistant", tool_reply)
            yield tool_reply
            return

        from src.routines import routine_engine
        sub_commands = routine_engine.decompose_compound_command(user_text)
        if len(sub_commands) > 1:
            for sub_cmd in sub_commands:
                if cancel_event and cancel_event.is_set():
                    break
                for s in self.process_message_stream(sub_cmd, cancel_event=cancel_event):
                    yield s
            return

        accumulated = []
        for sentence in brain.stream_chat(user_text, cancel_event=cancel_event):
            if cancel_event and cancel_event.is_set():
                break
            accumulated.append(sentence)
            yield sentence

        if accumulated:
            full_reply = " ".join(accumulated).strip()
            self._save_turn("assistant", full_reply)

    def record_interruption(self, partial_spoken_text: str) -> None:
        """Records that the assistant was interrupted mid-speech."""
        brain.record_interruption(partial_spoken_text)
        cut_text = (partial_spoken_text or "").strip()
        interrupted_msg = f"{cut_text}... [interrupted]" if cut_text else "[interrupted before speaking]"
        if self.persistent_history and self.persistent_history[-1].get("role") == "assistant":
            self.persistent_history[-1]["content"] = interrupted_msg
        else:
            self.persistent_history.append({
                "timestamp": datetime.now().isoformat(),
                "role": "assistant",
                "content": interrupted_msg,
            })
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.persistent_history, f, indent=2)
        except Exception as e:
            print(f"[Agent] Failed to update chat history on interruption: {e}")


# Global singleton
agent = HomeAgent()
