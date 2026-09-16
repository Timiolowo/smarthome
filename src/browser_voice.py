"""Local speech transcription and turn handling for the browser voice client."""

import base64
import binascii
import io
import os
import re
import threading
import wave

import numpy as np

from src.agent import agent
from src.interruption import response_interruption
from src.memory import memory


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_STT_DIR = os.path.join(PROJECT_ROOT, "models", "stt")


class BrowserVoice:
    """Owns the local STT model used by browser-recorded turns."""

    def __init__(self):
        self._model = None
        self._model_lock = threading.Lock()
        self._turn_lock = threading.Lock()
        self.loading_state = "IDLE"
        self.loading_error = None

    def preload_async(self):
        """Asynchronously warms up Faster-Whisper so it is ready before user speaks."""
        t = threading.Thread(target=self._get_model, daemon=True, name="FasterWhisperPreloader")
        t.start()

    def status(self) -> dict:
        return {
            "state": self.loading_state,
            "ready": self._model is not None,
            "error": self.loading_error,
        }

    def _get_model(self):
        with self._model_lock:
            if self._model is None:
                model_path = os.path.join(LOCAL_STT_DIR, "model.bin")
                if not os.path.exists(model_path):
                    self.loading_state = "ERROR"
                    self.loading_error = "Local Faster-Whisper model is not installed"
                    raise RuntimeError(self.loading_error)
                self.loading_state = "LOADING"
                memory.update_assistant_runtime(runtime_state="LOADING_SPEECH_MODEL")
                try:
                    from faster_whisper import WhisperModel
                    print("[BrowserVoice] Loading local Faster-Whisper...")
                    self._model = WhisperModel(LOCAL_STT_DIR, device="cpu", compute_type="int8", cpu_threads=4)
                    self.loading_state = "READY"
                    memory.update_assistant_runtime(runtime_state="IDLE")
                    print("[BrowserVoice] Local Faster-Whisper loaded and READY.")
                except Exception as e:
                    self.loading_state = "ERROR"
                    self.loading_error = str(e)
                    print(f"[BrowserVoice] Failed to load Faster-Whisper: {e}")
                    raise
            return self._model

    @staticmethod
    def _decode_wav(encoded_audio: str) -> np.ndarray:
        try:
            payload = base64.b64decode(encoded_audio, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Invalid browser audio encoding") from exc
        if len(payload) > 2_000_000:
            raise ValueError("Browser audio turn is too large")
        try:
            with wave.open(io.BytesIO(payload), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
                if channels != 1 or sample_width != 2 or sample_rate != 16000:
                    raise ValueError("Browser audio must be mono 16 kHz PCM")
                if frame_count < 1600 or frame_count > 16_000 * 60:
                    raise ValueError("Browser audio must be between 0.1 and 60 seconds")
                samples = np.frombuffer(wav_file.readframes(frame_count), dtype="<i2")
        except (EOFError, wave.Error) as exc:
            raise ValueError("Invalid browser WAV audio") from exc
        return samples.astype(np.float32) / 32768.0

    def transcribe(self, encoded_audio: str) -> str:
        samples = self._decode_wav(encoded_audio)
        segments, _ = self._get_model().transcribe(
            samples,
            beam_size=1,
            language="en",
            condition_on_previous_text=False,
            temperature=0,
            no_speech_threshold=.6,
        )
        accepted = [
            segment.text.strip()
            for segment in segments
            if segment.text.strip() and segment.avg_logprob >= -1.0 and segment.no_speech_prob <= .6
        ]
        return " ".join(accepted).strip().lower()

    def process_turn(self, encoded_audio: str, mode: str, wake_phrases, assistant_name: str, user_name: str) -> dict:
        """Transcribe one browser turn, apply wake-mode rules, and generate a cancellable reply."""
        with self._turn_lock:
            memory.update_assistant_runtime(runtime_state="TRANSCRIBING")
            transcript = self.transcribe(encoded_audio)
            if not transcript:
                return {"ok": True, "heard": "", "reply": "", "ignored": True}

            normalized_phrases = sorted(
                list(dict.fromkeys([phrase.lower().strip() for phrase in wake_phrases if phrase.strip()] + [assistant_name.lower()])),
                key=len,
                reverse=True
            )
            heard_wake = None
            for phrase in normalized_phrases:
                pattern = rf"\b{re.escape(phrase)}\b"
                match = re.search(pattern, transcript, re.IGNORECASE)
                if match:
                    heard_wake = match.group(0).lower()
                    break

            if mode == "wake" and not heard_wake:
                return {"ok": True, "heard": transcript, "reply": "", "ignored": True}

            command = transcript
            if heard_wake:
                pattern = rf"^(?:.*?\b){re.escape(heard_wake)}\b[\s,.]*"
                command = re.sub(pattern, "", command, flags=re.IGNORECASE).strip(" ,.!?")

            if not command:
                ack_reply = f"Yes, {user_name}?"
                print(f"\n🎤 [Heard]: \"{transcript}\" (Wake phrase)")
                print(f"🤖 [{assistant_name}]: \"{ack_reply}\"")
                return {"ok": True, "heard": transcript, "reply": ack_reply, "wake": True}

            print(f"\n🎤 [Heard]: \"{transcript}\"")
            if command != transcript:
                print(f"👉 [Command]: \"{command}\"")

            clean_cmd = re.sub(r"[^\w\s]", " ", command.lower()).strip()
            standby_patterns = [
                r"\b(?:go\s+(?:on\s+|to\s+)?standby|enter\s+standby|activate\s+standby|switch\s+to\s+standby|standby\s+mode|standby)\b",
                r"\b(?:go\s+to\s+sleep|sleep\s+mode|enter\s+sleep|activate\s+sleep)\b",
                r"\b(?:put\s+(?:the\s+)?(?:screen|display|system)?\s*(?:to\s+sleep|on\s+standby))\b",
            ]
            is_explicit_standby = any(re.search(pat, clean_cmd) for pat in standby_patterns)
            dismissal_keywords = {
                "stop", "that's all", "thats all", "goodnight", "good night", "bye", "goodbye",
                "nothing", "nevermind", "never mind", "cancel", "sleep", "go to sleep", "standby",
                "fine nothing", "okay fine nothing", "ok fine nothing", "nothing for now",
                "nothing else", "no nothing", "mean nothing", "nothing thanks", "nothing thank you"
            }
            is_dismissal = is_explicit_standby or clean_cmd in dismissal_keywords or any(
                clean_cmd.endswith(term) or clean_cmd.startswith(term) for term in ["nothing", "nevermind", "never mind", "thats all", "that's all", "goodnight", "good night", "bye", "goodbye", "cancel", "stop", "sleep", "standby"]
            )

            if is_dismissal:
                farewell = "Going into ambient standby mode now. Sleeping display." if is_explicit_standby else "Alright, standing by."
                print(f"🤖 [{assistant_name}]: \"{farewell}\"")
                return {
                    "ok": True,
                    "heard": transcript,
                    "reply": farewell,
                    "wake": False,
                    "end_conversation": True,
                    "standby": True,
                }

            memory.update_assistant_runtime(runtime_state="THINKING", last_heard=transcript)
            cancel_event = response_interruption.begin_response()
            sentences = []
            try:
                for sentence in agent.process_message_stream(command, cancel_event=cancel_event):
                    if cancel_event.is_set():
                        break
                    sentences.append(sentence)
            finally:
                response_interruption.finish_response(cancel_event)

            reply = " ".join(sentences).strip()
            interrupted = cancel_event.is_set()
            if interrupted:
                agent.record_interruption(reply)
                print(f"🛑 [{assistant_name} Interrupted]: \"{reply}\"... [interrupted]")
            else:
                print(f"🤖 [{assistant_name}]: \"{reply}\"")

            is_reply_standby = bool(re.search(r"\b(?:standby\s+mode|ambient\s+standby|sleeping\s+display|standing\s+by)\b", reply.lower()))

            memory.update_assistant_runtime(
                runtime_state="LISTENING" if interrupted else "SPEAKING",
                last_heard=transcript,
                last_reply=f"{reply}... [interrupted]" if interrupted and reply else reply,
            )
            return {
                "ok": True,
                "heard": transcript,
                "reply": reply,
                "interrupted": interrupted,
                "ignored": False,
                "wake": bool(heard_wake) and not is_reply_standby,
                "end_conversation": is_reply_standby,
                "standby": is_reply_standby,
            }


browser_voice = BrowserVoice()
