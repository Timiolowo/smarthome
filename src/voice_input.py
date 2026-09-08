import os
import select
import sys
import time
from typing import List, Optional

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

LOCAL_STT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "stt",
)


class VoiceListener:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.recognizer = sr.Recognizer() if sr else None
        self.whisper_model = None
        self.available = False
        self.silence_threshold = 500

        # Try initializing local Faster-Whisper first
        if WhisperModel and os.path.exists(LOCAL_STT_DIR) and os.path.exists(os.path.join(LOCAL_STT_DIR, "model.bin")):
            try:
                print(f"[VoiceListener] Loading local Faster-Whisper model from {LOCAL_STT_DIR}...")
                self.whisper_model = WhisperModel(LOCAL_STT_DIR, device="cpu", compute_type="int8")
                print("[VoiceListener] Local Faster-Whisper ready (offline STT).")
            except Exception as e:
                print(f"[VoiceListener] Notice: Failed to load local Whisper ({e}), falling back to Google Speech.")

        if sd is not None:
            try:
                sd.check_input_settings(samplerate=self.sample_rate, channels=1)
                self.available = True
            except Exception as e:
                print(f"[VoiceListener] Warning: Sound device check failed: {e}")

    def calibrate(self, duration: float = 1.0) -> None:
        """Calibrates baseline ambient noise level."""
        if not self.available:
            return
        try:
            print("[VoiceListener] Calibrating microphone for ambient room noise (1 sec)...")
            recording = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
            )
            sd.wait()
            rms = np.sqrt(np.mean(recording.astype(np.float64) ** 2))
            self.silence_threshold = max(300, int(rms * 1.5))
            print(f"[VoiceListener] Microphone calibrated. Noise threshold: {self.silence_threshold}")
        except Exception as e:
            print(f"[VoiceListener] Calibration failed ({e}), using default threshold {self.silence_threshold}.")

    def _check_keyboard(self) -> bool:
        """Non-blocking check if Enter or Space was pressed."""
        try:
            r, _, _ = select.select([sys.stdin], [], [], 0.0)
            if r:
                sys.stdin.readline()
                return True
        except Exception:
            pass
        return False

    def monitor_for_interruption(self, speech_process) -> bool:
        """
        Monitors microphone and keyboard while speech_process is running.
        Returns True immediately if the user speaks or taps a key.
        """
        if not self.available:
            while speech_process.poll() is None:
                if self._check_keyboard():
                    return True
                time.sleep(0.05)
            return False

        chunk_size = int(0.1 * self.sample_rate)
        # Interrupt threshold: 2.5x ambient noise to avoid speaker self-echo
        interrupt_threshold = max(850, int(self.silence_threshold * 2.5))
        consecutive_chunks = 0

        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="int16") as stream:
                while speech_process.poll() is None:
                    # 1. Check keyboard hit
                    if self._check_keyboard():
                        return True

                    # 2. Check microphone audio level
                    data, _ = stream.read(chunk_size)
                    chunk = data.flatten()
                    rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))

                    if rms > interrupt_threshold:
                        consecutive_chunks += 1
                        # 2 consecutive chunks (~200ms) = deliberate speech
                        if consecutive_chunks >= 2:
                            return True
                    else:
                        consecutive_chunks = 0
        except Exception:
            pass

        return False

    def listen_once(self, timeout: int = 7, phrase_time_limit: int = 5) -> Optional[str]:
        """Listens for speech and transcribes using local Whisper or Google fallback."""
        if not self.available:
            print("\n[VoiceListener] (Microphone unavailable) Type your command (or press Enter to skip): ", end="", flush=True)
            try:
                line = sys.stdin.readline().strip().lower()
                return line if line else None
            except Exception:
                return None

        chunk_duration = 0.1
        chunk_size = int(chunk_duration * self.sample_rate)
        
        frames = []
        speech_started = False
        silence_start_time = None
        start_time = time.time()
        phrase_start_time = None

        print("🎤 [Listening...] Speak now into your microphone...")

        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="int16") as stream:
                while True:
                    data, overflowed = stream.read(chunk_size)
                    chunk = data.flatten()
                    rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))

                    now = time.time()

                    if not speech_started:
                        if rms > self.silence_threshold:
                            speech_started = True
                            phrase_start_time = now
                            frames.append(chunk)
                        elif (now - start_time) > timeout:
                            return None
                    else:
                        frames.append(chunk)

                        if rms < self.silence_threshold:
                            if silence_start_time is None:
                                silence_start_time = now
                            elif (now - silence_start_time) > 1.0:
                                break
                        else:
                            silence_start_time = None

                        if (now - phrase_start_time) > phrase_time_limit:
                            break

        except Exception as e:
            print(f"[VoiceListener] Audio recording error: {e}")
            return None

        if not frames:
            return None

        print("⏳ [Processing speech offline...]")
        full_audio = np.concatenate(frames)

        # 1. Local Faster-Whisper
        if self.whisper_model is not None:
            try:
                audio_float32 = full_audio.astype(np.float32) / 32768.0
                segments, _ = self.whisper_model.transcribe(
                    audio_float32,
                    beam_size=1,
                    language="en",
                    initial_prompt="Nigerian English, conversational speech about smart home, movies like Silo, Merlin, power, battery, timers, food.",
                )
                text = " ".join(seg.text for seg in segments).strip()
                if text:
                    print(f"🗣️ [Recognized (Local Whisper)]: \"{text}\"")
                    return text.lower()
                return None
            except Exception as e:
                print(f"[VoiceListener] Local Whisper error ({e}), trying fallback...")

        # 2. Google Speech Recognition fallback
        if self.recognizer is not None and sr is not None:
            try:
                audio_bytes = full_audio.tobytes()
                audio_data = sr.AudioData(audio_bytes, self.sample_rate, 2)
                text = self.recognizer.recognize_google(audio_data)
                print(f"🗣️ [Recognized (Google)]: \"{text}\"")
                return text.lower()
            except Exception:
                return None

        return None

    def wait_for_trigger(
        self,
        triggers: List[str],
        timeout: int = 7,
        phrase_time_limit: int = 5,
    ) -> bool:
        """Listens and returns True if any trigger word is detected in speech."""
        spoken = self.listen_once(timeout=timeout, phrase_time_limit=phrase_time_limit)
        if not spoken:
            return False

        for trigger in triggers:
            if trigger.lower() in spoken:
                return True
        return False
