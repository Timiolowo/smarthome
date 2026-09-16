import os
import re
import select
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from src import audio_runtime
from src.audio_capture import AudioCapture
from src.audio_capabilities import interruption_capabilities

try:
    from faster_whisper import WhisperModel
    from faster_whisper.vad import get_vad_model
except ImportError:
    WhisperModel = None
    get_vad_model = None

LOCAL_STT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'stt')


def strip_greeting(text: str, triggers: List[str]) -> str:
    """Remove leading wake phrases while preserving the user's command."""
    alternatives = '|'.join(re.escape(t) for t in sorted(triggers, key=len, reverse=True) if t)
    if not alternatives:
        return text.strip()
    return re.sub(rf'^(?:\s*(?:{alternatives})\b[\s,.!?]*)+', '', text, flags=re.IGNORECASE).strip()


def is_conversation_exit(text: str, phrases: List[str]) -> bool:
    return text.lower().strip().rstrip('.!?,').strip() in phrases


@dataclass
class ListenResult:
    status: str = 'silence'  # speech, silence, unclear, error, truncated
    text: str = ''
    message: str = ''


class SpeechDetector:
    """Use the bundled Silero model, not loudness, to identify speech."""
    def __init__(self):
        self.model = get_vad_model() if get_vad_model else None
        if self.model is None:
            raise RuntimeError('Speech detection requires faster-whisper and onnxruntime')
        self.reset()

    def reset(self):
        self.window = deque(maxlen=16)

    def probability(self, frame):
        self.window.append(frame)
        # The bundled callable owns its recurrent state. A rolling context keeps
        # compatibility across Faster-Whisper model versions without private APIs.
        audio = np.concatenate(list(self.window))
        audio = np.pad(audio, (0, (-len(audio)) % 512)).astype(np.float32)
        return float(np.asarray(self.model(audio)).reshape(-1)[-1])


def endpoint_delay(text, patient_pause=0.85):
    """Snappy endpoint for finished speech; preserves natural thinking pauses."""
    words = re.findall(r"[\w']+", text.lower())
    unfinished = {'and', 'or', 'but', 'because', 'if', 'for', 'to', 'with', 'a', 'the', 'in', 'at', 'uh', 'um'}
    if not words or words[-1] in unfinished or words[-1].isdigit():
        return max(patient_pause, 1.2)
    if text.rstrip().endswith('?') and len(words) >= 3:
        return 0.55
    return patient_pause


class VoiceListener:
    def __init__(self, sample_rate=16000, device=None, echo_cancellation=True,
                 ready_chime=False, feedback=None, load_model=True):
        self.sample_rate = sample_rate
        self.device = device
        self.echo_cancellation_requested = echo_cancellation
        self._native_recovery_attempted = False
        self.available = False
        self.capture = None
        self.whisper_model = None
        self.detector = None
        self.last_result = ListenResult()
        self.silence_threshold = 80
        self.noise_rms = 0.0
        self.ready_chime = ready_chime
        self.feedback = feedback
        self.pending_audio = []
        self._last_meter = 0
        self._last_state = None
        try:
            self.detector = SpeechDetector()
            self.capture = AudioCapture(device=device, echo_cancellation=echo_cancellation)
            self.available = True
            audio_runtime.publish(device=self.capture.name, echo_cancelled=self.capture.echo_cancelled,
                                  interruption=interruption_capabilities(self.capture.echo_cancelled),
                                  detector='Silero', state='STARTING', message='Preparing microphone')
            print(f'[Audio] Microphone: {self.capture.name}; echo cancellation: {self.capture.echo_cancelled}')
        except Exception as exc:
            audio_runtime.publish(state='ERROR', message=str(exc))
            print(f'[VoiceListener] {exc}. Typed input is available.')
        if load_model and WhisperModel and os.path.exists(os.path.join(LOCAL_STT_DIR, 'model.bin')):
            try:
                print('[VoiceListener] Loading local Faster-Whisper...')
                self.whisper_model = WhisperModel(LOCAL_STT_DIR, device='cpu', compute_type='int8')
            except Exception as exc:
                print(f'[VoiceListener] Local transcription unavailable: {exc}')
        self.calibrated = False

    def _replace_capture(self, echo_cancellation):
        if self.capture:
            self.capture.close()
        self.capture = AudioCapture(
            device=None if echo_cancellation else self.device,
            echo_cancellation=echo_cancellation,
        )
        self.available = True
        audio_runtime.publish(
            device=self.capture.name,
            echo_cancelled=self.capture.echo_cancelled,
            interruption=interruption_capabilities(self.capture.echo_cancelled),
            state='STARTING',
            message='Reconnecting microphone',
        )
        print(f'[Audio] Microphone: {self.capture.name}; echo cancellation: {self.capture.echo_cancelled}')

    def _state(self, state, message):
        audio_runtime.publish(state=state, message=message)
        if self._last_state != state:
            self._last_state = state
            if self.feedback:
                self.feedback(state)

    def _meter(self, frame, probability):
        now = time.monotonic()
        if now - self._last_meter >= 0.2:
            rms = float(np.sqrt(np.mean(frame ** 2)))
            audio_runtime.publish(level_db=round(20 * np.log10(max(rms, 1e-7)), 1),
                                  speech_probability=round(probability, 2),
                                  clipping=bool(np.max(np.abs(frame)) >= .99),
                                  dropped_frames=self.capture.dropped_frames)
            self._last_meter = now

    def calibrate(self, duration=1.5):
        if not self.available:
            return
        self._state('CALIBRATING', 'Stay quiet briefly while I check the room')
        print('[Audio] Stay quiet for microphone calibration...')
        try:
            self.capture.flush()
            levels = []
            peak = 0.0
            for _ in range(int(duration * self.sample_rate / 512)):
                frame = self.capture.read()
                levels.append(float(np.sqrt(np.mean(frame ** 2))))
                peak = max(peak, float(np.max(np.abs(frame))))
            if peak < 1e-6:
                import platform, subprocess
                os_name = platform.system()
                if os_name == 'Darwin' and self.capture.echo_cancelled:
                    if not self._native_recovery_attempted:
                        self._native_recovery_attempted = True
                        print('[Audio] Voice-processing input returned silence; recreating the audio route once...')
                        self._replace_capture(echo_cancellation=True)
                        return self.calibrate(duration)

                    print('[Audio] Voice-processing input is still silent; using the standard microphone without voice interruption.')
                    self._replace_capture(echo_cancellation=False)
                    return self.calibrate(duration)

                self.available = False
                if os_name == 'Darwin':
                    message = ('The standard microphone is returning digital silence. '
                               'Open System Settings → Privacy & Security → Microphone and enable the app '
                               'this was launched from (e.g. Terminal), then restart. Typed input still works.')
                    try:
                        subprocess.Popen(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone'])
                    except Exception:
                        pass
                elif os_name == 'Windows':
                    message = ('Microphone is muted or blocked by Windows. '
                               'Check Windows Settings → Privacy & Security → Microphone to allow desktop apps access. Typed input still works.')
                    try:
                        subprocess.Popen(['start', 'ms-settings:privacy-microphone'], shell=True)
                    except Exception:
                        pass
                elif os_name == 'Linux':
                    message = ('Microphone is receiving digital silence. '
                               'Check your audio mixer (PulseAudio, PipeWire, or ALSA) capture volume and permissions. Typed input still works.')
                else:
                    message = ('Microphone is receiving digital silence. '
                               'Please verify your microphone is unmuted and OS permissions are enabled. Typed input still works.')

                self.last_result = ListenResult('error', message=message)
                self._state('ERROR', message)
                print(f'\n[Audio] {message}')
                return
            self.noise_rms = float(np.median(levels))
            self.silence_threshold = max(80, int(self.noise_rms * 32768 * 1.25))
            self.calibrated = True
            audio_runtime.publish(noise_db=round(20 * np.log10(max(self.noise_rms, 1e-7)), 1))
            self.detector.reset()
        except Exception as exc:
            self.last_result = ListenResult('error', message=str(exc))
            self._state('ERROR', str(exc))

    def diagnose(self):
        if not self.available:
            print('No microphone available. Check the OS input device and microphone permission for your terminal.')
            return False
        self.calibrate(3)
        if not self.calibrated:
            return False
        print('Now speak normally for five seconds: "Hello, can you hear me comfortably?"')
        self._state('LISTENING', 'Speak normally for five seconds')
        levels, probabilities, peaks = [], [], []
        self.capture.flush()
        try:
            for _ in range(int(5 * self.sample_rate / 512)):
                frame = self.capture.read()
                probability = self.detector.probability(frame)
                levels.append(float(np.sqrt(np.mean(frame ** 2))))
                peaks.append(float(np.max(np.abs(frame))))
                probabilities.append(probability)
                self._meter(frame, probability)
        except Exception as exc:
            self._state('ERROR', str(exc))
            print(f'Microphone check failed: {exc}')
            return False
        speech_levels = [level for level, probability in zip(levels, probabilities) if probability >= .5]
        signal = float(np.median(speech_levels)) if speech_levels else 0
        snr = 20 * np.log10(max(signal, 1e-7) / max(self.noise_rms, 1e-7))
        if max(peaks) >= .99:
            advice = 'Input is clipping. Lower the microphone input level slightly.'
        elif not speech_levels:
            advice = 'No clear speech detected. Check the selected input device and input volume.'
        elif snr < 10:
            advice = 'Speech is close to room noise. Move the microphone closer or reduce background noise.'
        else:
            advice = 'Normal-volume speech is registering clearly in this sample.'
        audio_runtime.publish(diagnostic=advice, signal_to_noise_db=round(float(snr), 1))
        print(f'Microphone: {self.capture.name}\nSpeech/noise separation: {snr:.1f} dB\n{advice}')
        return bool(speech_levels)

    def _check_keyboard(self):
        try:
            if sys.stdin.isatty() and select.select([sys.stdin], [], [], 0)[0]:
                return bool(sys.stdin.readline())
        except (OSError, ValueError):
            pass
        return False

    def monitor_for_interruption(self, speech_process, allow_voice=True):
        """Keyboard works everywhere; voice barge-in requires echo-cancelled capture."""
        can_listen = allow_voice and self.available and self.capture.echo_cancelled
        if can_listen:
            self.capture.flush()
            self.detector.reset()
        recent = deque(maxlen=16)
        consecutive = 0
        while speech_process.poll() is None:
            if self._check_keyboard():
                return True
            if not can_listen:
                time.sleep(.03)
                continue
            try:
                frame = self.capture.read()
                recent.append(frame.copy())
                probability = self.detector.probability(frame)
                self._meter(frame, probability)
                consecutive = consecutive + 1 if probability >= .65 else 0
                if consecutive >= 6:  # ~190 ms of speech after echo cancellation.
                    self.pending_audio = list(recent)
                    return True
            except Exception as exc:
                audio_runtime.publish(message=f'Voice interruption unavailable: {exc}')
                can_listen = False
        return False

    def _transcribe(self, frames):
        if self.whisper_model is None:
            return ListenResult('error', message='Local speech model is unavailable; use typed input or restore models/stt.')
        started = time.monotonic()
        try:
            audio = np.concatenate(frames).astype(np.float32)
            segments, _ = self.whisper_model.transcribe(
                audio, beam_size=1, language='en', condition_on_previous_text=False,
                temperature=0, no_speech_threshold=.6,
            )
            segments = list(segments)
            text = ' '.join(s.text for s in segments).strip()
            confident = bool(segments) and all(s.avg_logprob >= -1.0 and s.no_speech_prob <= .6 for s in segments)
            if text and confident:
                return ListenResult('speech', text.lower())
            return ListenResult('unclear', message='I heard speech but could not make out the words')
        except Exception as exc:
            return ListenResult('error', message=f'Transcription failed: {exc}')
        finally:
            audio_runtime.timing('transcription', time.monotonic() - started)

    def listen_once(self, timeout=30, phrase_time_limit=25, cue=False, cancel_event=None,
                    state_message='Listening — speak normally', console_message='🎤 Listening — speak normally...'):
        self.last_result = ListenResult()
        if cancel_event and cancel_event.is_set():
            self.last_result = ListenResult('cancelled')
            return None
        if not self.available:
            self._state('ERROR', 'Microphone unavailable — type in the terminal or dashboard')
            print('[VoiceListener] Type your message: ', end='', flush=True)
            try:
                line = sys.stdin.readline()
                if not line:
                    raise KeyboardInterrupt
                text = line.strip().lower()
                self.last_result = ListenResult('speech', text) if text else ListenResult()
                return text or None
            except (OSError, ValueError) as exc:
                self.last_result = ListenResult('error', message=str(exc))
                return None
        frames = list(self.pending_audio)
        self.pending_audio = []
        if not frames:
            self.capture.flush()
            self.detector.reset()
            if cue and self.ready_chime:
                from src.voice_output import play_ready_chime
                play_ready_chime(self.capture)
                self.capture.flush()
        self._state('LISTENING', state_message)
        print(console_message)
        pre_roll = deque(maxlen=12)
        active = bool(frames)
        consecutive = 0
        elapsed = len(frames) * .032
        silence = 0.0
        patient_pause = 0.85
        preview = None
        last_voice = len(frames)
        speech_end_at = time.monotonic()
        overflow_at_start = self.capture.dropped_frames
        try:
            while True:
                if cancel_event and cancel_event.is_set():
                    self.last_result = ListenResult('cancelled')
                    return None
                frame = self.capture.read()
                probability = self.detector.probability(frame)
                self._meter(frame, probability)
                voiced = probability >= (.35 if active else .5)
                if not active:
                    pre_roll.append(frame.copy())
                    elapsed += .032
                    consecutive = consecutive + 1 if voiced else 0
                    if consecutive >= 3:
                        active = True
                        frames = list(pre_roll)
                        elapsed = len(frames) * .032
                        last_voice = len(frames)
                        speech_end_at = time.monotonic()
                        self._state('HEARING', 'I can hear you')
                    elif elapsed >= timeout:
                        return None
                    continue
                frames.append(frame.copy())
                elapsed += .032
                if voiced:
                    if silence > .4:
                        patient_pause = min(1.8, max(patient_pause, silence + .3))
                    silence = 0
                    preview = None
                    last_voice = len(frames)
                    speech_end_at = time.monotonic()
                    self._state('HEARING', 'I can hear you')
                else:
                    silence += .032
                    if silence >= 0.55 and preview is None:
                        self._state('TRANSCRIBING', 'Checking what you said')
                        preview = self._transcribe(frames[:last_voice + 6])
                        self._state('LISTENING', 'You can continue speaking')
                    delay = endpoint_delay(preview.text if preview else '', patient_pause)
                    if silence >= delay:
                        break
                if elapsed >= phrase_time_limit:
                    self.last_result = ListenResult('truncated', message='That was longer than one listening turn')
                    return None
            self._state('TRANSCRIBING', 'Understanding your words')
            self.last_result = preview or self._transcribe(frames)
            if self.capture.dropped_frames > overflow_at_start:
                self.last_result = ListenResult('unclear', message='Some microphone audio was dropped; please repeat that')
            audio_runtime.timing('end_of_turn', time.monotonic() - speech_end_at)
            if self.last_result.text:
                print(f'🗣️ Heard: "{self.last_result.text}"')
                return self.last_result.text
            if self.last_result.status == 'error':
                self._state('ERROR', self.last_result.message)
            return None
        except Exception as exc:
            self.last_result = ListenResult('error', message=f'Microphone error: {exc}')
            self._state('ERROR', self.last_result.message)
            return None

    def wait_for_trigger(self, triggers: List[str], timeout=7, phrase_time_limit=25,
                         cancel_event=None, wake_name=None) -> Optional[str]:
        display_name = wake_name or 'wake phrase'
        spoken = self.listen_once(timeout=timeout, phrase_time_limit=phrase_time_limit,
                                  cancel_event=cancel_event,
                                  state_message=f'Waiting for “{display_name}”',
                                  console_message=f'💤 Waiting for “{display_name}” — say the wake phrase...')
        if spoken:
            for trigger in triggers:
                if trigger and re.search(rf'\b{re.escape(trigger)}\b', spoken, re.IGNORECASE):
                    return spoken
        return None

    def close(self):
        if self.capture:
            self.capture.close()
        audio_runtime.publish(state='OFFLINE', message='Voice listener stopped')
