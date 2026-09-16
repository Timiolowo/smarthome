import argparse
import os
import threading
import time

from src.config import load_config
from src import audio_runtime
from src.interruption import response_interruption
from src.terminal_logger import terminal_logger
from src.voice_input import VoiceListener, strip_greeting, is_conversation_exit

EXIT_PHRASES = ["that's all", 'thats all', 'goodnight', 'good night', 'bye', 'goodbye',
                'stop', "i'm good", 'im good', 'nothing', 'nothing else', 'never mind', 'nevermind',
                'fine nothing', 'cancel', 'sleep', 'standby']
WAKE_TRIGGERS = ['hey', 'hello', 'hi', 'assistant', 'good morning', 'good afternoon', 'good evening']


def run_assistant_loop(stop_event=None, simulate_presence=False):
    """Core voice assistant loop. Exits cleanly when stop_event is set."""
    from src.agent import agent
    from src.brain import brain
    from src.memory import memory
    from src.presence import PresenceTracker
    from src.system_power import system_power
    from src.voice_output import speak, stop
    try:
        from src.voice_output import speak_stream
    except ImportError:
        speak_stream = None

    stop_event = stop_event or threading.Event()
    config = load_config()
    assistant_name = memory.load_assistant().get('name', 'Nova')
    wake_triggers = list(dict.fromkeys(config.trigger_phrases + WAKE_TRIGGERS + [assistant_name.lower()]))
    print(f'\n🏡 HOME AI ASSISTANT — {config.user_name}')
    print(f'Wake phrases: {", ".join(wake_triggers)}')
    print(f'Brain: {brain.provider_name} ({brain.model_name})' if brain.available else 'Brain: Unavailable (tools still work)')
    print('Press Enter while I speak to interrupt. Voice interruption uses echo cancellation when available.')
    tracker = PresenceTracker(target_ip=config.phone_ip, debounce_count=config.presence_debounce_count)
    listener = None
    state = 'AWAY'
    failures = 0
    system_power.mark_voice_loop_started()

    def open_listener():
        new_listener = VoiceListener(
            device=config.microphone_device,
            echo_cancellation=config.echo_cancellation,
            ready_chime=config.ready_chime,
            feedback=lambda value: memory.update_assistant_runtime(runtime_state=value),
        )
        new_listener.calibrate()
        return new_listener

    def set_state(value, message):
        audio_runtime.publish(state=value, message=message, voice_mode=system_power.voice_mode())
        memory.update_assistant_runtime(runtime_state=value)

    def respond(text=None, reply=None):
        if text:
            set_state('THINKING', 'Thinking about your request')
            memory.update_assistant_runtime(runtime_state='THINKING', last_heard=text)
            started = time.monotonic()
            cancel_event = response_interruption.begin_response()
            # If speak_stream is available and agent has process_message_stream, use sentence-streaming with cancellation
            if speak_stream is not None and hasattr(agent, 'process_message_stream'):
                stream = agent.process_message_stream(text, cancel_event=cancel_event)
                interrupted, spoken_text = speak_stream(
                    stream,
                    listener=listener,
                    interruptible=True,
                    voice=config.voice_name,
                    cancel_event=cancel_event,
                )
            else:
                reply = agent.process_message(text)
                interrupted = speak(reply, listener=listener, interruptible=True, voice=config.voice_name)
                spoken_text = reply

            response_interruption.finish_response(cancel_event)

            audio_runtime.timing('response', time.monotonic() - started)
            if interrupted:
                if hasattr(agent, 'record_interruption'):
                    agent.record_interruption(spoken_text)
                audio_runtime.publish(interrupted=True)
                set_state('LISTENING', 'Interrupted — listening to your new request')
                memory.update_assistant_runtime(runtime_state='LISTENING', last_reply=f"{spoken_text}... [interrupted]")
            else:
                audio_runtime.publish(interrupted=False)
                memory.update_assistant_runtime(runtime_state='SPEAKING', last_reply=spoken_text)
                set_state('LISTENING', 'Listening — speak normally')
            return interrupted
        else:
            audio_runtime.timing('response', 0)
            memory.update_assistant_runtime(runtime_state='SPEAKING', last_reply=reply)
            interrupted = speak(reply, listener=listener, interruptible=True, voice=config.voice_name)
            audio_runtime.publish(interrupted=bool(interrupted))
            set_state('LISTENING', 'Listening — speak normally')
            return interrupted

    def recover():
        nonlocal failures
        result = listener.last_result
        if result.status == 'silence':
            failures = 0
            return False
        failures += 1
        if result.status == 'error':
            set_state('ERROR', result.message)
            print(f'[Audio] {result.message}')
            if failures == 1:
                respond(reply="I'm having trouble with the microphone or speech model. You can type your message in the dashboard or terminal.")
            listener.available = False
        elif failures == 1:
            respond(reply='Could you say that in a shorter sentence?' if result.status == 'truncated'
                    else "I didn't catch that clearly. Could you say it again?")
        else:
            set_state('LISTENING', 'Still listening — you can also type in the dashboard')
        return True

    try:
        while not stop_event.is_set():
            requested_mode = system_power.voice_mode()
            if system_power.voice_change_event.is_set():
                system_power.voice_change_event.clear()
                state = 'CONVERSING' if requested_mode == 'live' else 'HOME_STANDBY'

            if requested_mode == 'off':
                if listener is not None:
                    listener.close()
                    listener = None
                system_power.acknowledge_voice_mode('off')
                set_state('MICROPHONE_OFF', 'Microphone off')
                system_power.voice_change_event.wait(0.25)
                continue

            if listener is None:
                listener = open_listener()

            system_power.acknowledge_voice_mode(requested_mode)

            if requested_mode == 'live':
                state = 'CONVERSING'
            elif state == 'CONVERSING':
                state = 'HOME_STANDBY'

            is_home = requested_mode in {'wake', 'live'} or simulate_presence or tracker.update()
            if not is_home:
                if state != 'AWAY':
                    memory.update_presence(False)
                state = 'AWAY'
                set_state('AWAY', 'Waiting for arrival')
                time.sleep(config.presence_poll_interval_seconds)
                continue
            current_asst_name = memory.load_assistant().get("name", "Nova")
            current_triggers = list(dict.fromkeys(config.trigger_phrases + WAKE_TRIGGERS + [current_asst_name.lower()]))

            if state == 'AWAY':
                memory.update_presence(True)
                state = 'HOME_STANDBY'
                set_state('WAITING_FOR_NOVA', f'Waiting for “{current_asst_name}”')
            if state in ('WAITING_FOR_HELLO', 'HOME_STANDBY'):
                print(f'🎤 Listening for “{current_asst_name}”...')
                spoken = listener.wait_for_trigger(triggers=current_triggers,
                                                  timeout=config.listen_timeout_seconds,
                                                  phrase_time_limit=config.conversation_phrase_limit_seconds,
                                                  cancel_event=system_power.voice_change_event,
                                                  wake_name=current_asst_name)
                if listener.last_result.status == 'cancelled':
                    continue
                if not spoken:
                    if listener.last_result.status == 'error':
                        recover()
                    set_state('WAITING_FOR_NOVA', f'Waiting for “{current_asst_name}”')
                    continue
                command = strip_greeting(spoken, current_triggers)
                system_power.set_voice_mode('live', wait=False)
                system_power.voice_change_event.clear()
                if command:
                    respond(text=command)
                else:
                    respond(reply=f'Yes, {config.user_name}?')
                failures = 0
                state = 'CONVERSING'
            elif state == 'CONVERSING':
                print('🎤 Listening — speak normally...')
                said = listener.listen_once(timeout=config.conversation_timeout_seconds,
                                            phrase_time_limit=config.conversation_phrase_limit_seconds,
                                            cue=True,
                                            cancel_event=system_power.voice_change_event)
                if listener.last_result.status == 'cancelled':
                    continue
                if said:
                    failures = 0
                    if is_conversation_exit(said, EXIT_PHRASES):
                        respond(reply="Okay. I'm here when you need me.")
                        state = 'HOME_STANDBY'
                        system_power.set_voice_mode('wake', wait=False)
                        system_power.voice_change_event.clear()
                        set_state('WAITING_FOR_NOVA', f'Waiting for “{current_asst_name}”')
                    else:
                        respond(text=said)
                elif not recover():
                    state = 'HOME_STANDBY'
                    system_power.set_voice_mode('wake', wait=False)
                    system_power.voice_change_event.clear()
                    set_state('WAITING_FOR_NOVA', f'Waiting for “{current_asst_name}”')
                    print(f'💤 Conversation paused. Say {current_asst_name} when you are ready.')
    finally:
        stop()
        if listener is not None:
            listener.close()
        system_power.mark_voice_loop_stopped()
        memory.update_assistant_runtime(runtime_state='OFFLINE')


def run_browser_backend_loop(stop_event=None, simulate_presence=False):
    """Keep the assistant backend alive while the browser owns all voice I/O."""
    from src.memory import memory
    from src.system_power import system_power
    from src.browser_voice import browser_voice

    # Pre-warm local speech model in background so first turn is instant
    browser_voice.preload_async()

    stop_event = stop_event or threading.Event()
    config = load_config()
    assistant_name = memory.load_assistant().get('name', 'Nova')
    print(f'\n🏡 HOME AI ASSISTANT — {config.user_name}')
    print('Brain: browser-controlled backend')
    print('Audio: Web UI only — the terminal microphone and speaker are disabled')
    print(f'Wake phrase: {assistant_name}')
    system_power.mark_voice_loop_started()
    last_mode = None
    try:
        while not stop_event.is_set():
            mode = system_power.voice_mode()
            if mode != last_mode or system_power.voice_change_event.is_set():
                system_power.voice_change_event.clear()
                system_power.acknowledge_voice_mode(mode)
                if mode == 'off':
                    audio_runtime.publish(state='MICROPHONE_OFF', message='Browser microphone off',
                                          voice_mode=mode, device='Browser microphone', echo_cancelled=False)
                    memory.update_assistant_runtime(runtime_state='MICROPHONE_OFF')
                elif mode == 'live':
                    audio_runtime.publish(state='LIVE_LISTENING', message='Browser live listening',
                                          voice_mode=mode, device='Browser microphone')
                    memory.update_assistant_runtime(runtime_state='LIVE_LISTENING')
                else:
                    audio_runtime.publish(state='WAITING_FOR_NOVA', message=f'Waiting for “{assistant_name}” in browser',
                                          voice_mode=mode, device='Browser microphone')
                    memory.update_assistant_runtime(runtime_state='WAITING_FOR_NOVA')
                last_mode = mode
            system_power.voice_change_event.wait(0.25)
    finally:
        system_power.mark_voice_loop_stopped()
        memory.update_assistant_runtime(runtime_state='OFFLINE')


def run_assistant(simulate_presence=False, audio_loop=None):
    from src.web_server import run_web_server
    from src.system_power import system_power

    server = run_web_server(host='0.0.0.0', port=5050, background=True, open_browser=True)
    audio_loop = audio_loop or run_browser_backend_loop
    system_power.register_loop_starter(audio_loop)
    system_power.prepare_for_direct_run(simulate_presence)

    try:
        audio_loop(system_power.stop_event, simulate_presence=simulate_presence)
        # If loop exited because of Power Off, keep server alive and wait for Power On or Ctrl+C
        while True:
            time.sleep(0.5)
            if system_power.worker_thread and system_power.worker_thread.is_alive():
                system_power.worker_thread.join(timeout=1.0)
    except KeyboardInterrupt:
        print('\nShutting down Home Assistant. Goodbye!')
    finally:
        system_power.power_off()
        if server:
            server.shutdown()
            server.server_close()


def main():
    parser = argparse.ArgumentParser(description='Home AI Assistant')
    parser.add_argument('--simulate-presence', action='store_true', help='Skip phone detection')
    parser.add_argument('--web-only', action='store_true', help='Run only the dashboard')
    parser.add_argument('--list-microphones', action='store_true', help='List available microphone names and IDs')
    parser.add_argument('--diagnose-audio', action='store_true', help='Check room noise and normal speaking volume')
    args = parser.parse_args()
    if args.list_microphones:
        import sounddevice as sd
        devices = [(i, d) for i, d in enumerate(sd.query_devices()) if d['max_input_channels'] > 0]
        for index, device in devices:
            print(f'{index}: {device["name"]}')
        if not devices:
            print('No microphones found. Check the OS input device and terminal microphone permission.')
        return
    if args.diagnose_audio:
        config = load_config()
        listener = VoiceListener(device=config.microphone_device, echo_cancellation=config.echo_cancellation,
                                 load_model=False)
        try:
            listener.diagnose()
        finally:
            listener.close()
        return
    if args.web_only:
        from src.web_server import run_web_server
        run_web_server(host='0.0.0.0', port=5050, background=False, open_browser=True)
        return
    run_assistant(simulate_presence=args.simulate_presence)


if __name__ == '__main__':
    main()
