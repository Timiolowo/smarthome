import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from src.voice_input import VoiceListener, ListenResult, endpoint_delay
from src.audio_capture import AudioCapture


class AudioTests(unittest.TestCase):
    def listener(self):
        with patch('src.voice_input.SpeechDetector'), patch('src.voice_input.AudioCapture'):
            listener = VoiceListener(load_model=False)
        listener.capture.dropped_frames = 0
        listener.capture.echo_cancelled = True
        return listener

    def run_audio(self, probabilities, result=None, seed=None):
        listener = self.listener()
        frames = iter(np.full(512, i / 10000, dtype=np.float32) for i in range(len(probabilities)))
        listener.capture.read.side_effect = lambda: next(frames)
        listener.detector.probability.side_effect = probabilities
        listener._transcribe = Mock(return_value=result or ListenResult('speech', 'hello there'))
        listener.pending_audio = seed or []
        with contextlib.redirect_stdout(io.StringIO()):
            text = listener.listen_once(timeout=1, phrase_time_limit=20)
        return listener, text

    def test_loud_non_speech_does_not_start_a_turn(self):
        listener, text = self.run_audio([0.01] * 40)
        self.assertIsNone(text)
        self.assertEqual(listener.last_result.status, 'silence')
        listener._transcribe.assert_not_called()

    def test_quiet_opening_audio_is_preserved(self):
        listener, text = self.run_audio([0] * 5 + [.9] * 12 + [0] * 80)
        self.assertEqual(text, 'hello there')
        recorded = listener._transcribe.call_args.args[0]
        self.assertEqual(float(recorded[0][0]), 0)

    def test_mid_sentence_pause_does_not_split_request(self):
        listener, text = self.run_audio([.9] * 10 + [0] * 45 + [.9] * 10 + [0] * 90,
                                       ListenResult('speech', 'set a timer for'))
        self.assertEqual(text, 'set a timer for')
        self.assertEqual(listener._transcribe.call_count, 2)
        self.assertGreater(len(listener._transcribe.call_args.args[0]), 60)

    def test_question_endpoint_is_faster_than_incomplete_phrase(self):
        self.assertLess(endpoint_delay('How are you?'), endpoint_delay('set a timer for'))
        self.assertEqual(endpoint_delay('set a timer for 5'), 2.2)

    def test_low_confidence_transcript_never_becomes_a_command(self):
        listener = self.listener()
        listener.whisper_model = Mock()
        listener.whisper_model.transcribe.return_value = ([SimpleNamespace(
            text='set a timer for 90 hours', avg_logprob=-1.7, no_speech_prob=.1)], None)
        result = listener._transcribe([np.zeros(512, dtype=np.float32)])
        self.assertEqual(result.status, 'unclear')
        self.assertEqual(result.text, '')

    def test_missing_model_is_an_error_not_silence(self):
        listener = self.listener()
        self.assertEqual(listener._transcribe([np.zeros(512)]).status, 'error')

    def test_interruption_keeps_the_start_of_user_speech(self):
        listener = self.listener()
        listener._check_keyboard = Mock(return_value=False)
        listener.capture.read.return_value = np.full(512, .05, dtype=np.float32)
        listener.detector.probability.return_value = .9
        playback = Mock()
        playback.poll.return_value = None
        self.assertTrue(listener.monitor_for_interruption(playback))
        self.assertEqual(len(listener.pending_audio), 6)
        seed = listener.pending_audio
        next_listener, text = self.run_audio([.9] * 5 + [0] * 80, seed=seed)
        self.assertEqual(text, 'hello there')
        next_listener.capture.flush.assert_not_called()

    def test_playback_without_echo_cancellation_ignores_microphone(self):
        listener = self.listener()
        listener.capture.echo_cancelled = False
        listener._check_keyboard = Mock(return_value=False)
        playback = Mock()
        playback.poll.side_effect = [None, 0]
        with patch('src.voice_input.time.sleep'):
            self.assertFalse(listener.monitor_for_interruption(playback))
        listener.capture.read.assert_not_called()

    def test_silent_native_route_recovers_with_standard_microphone(self):
        listener = self.listener()
        listener.capture.read.return_value = np.zeros(512, dtype=np.float32)

        retry_capture = Mock()
        retry_capture.name = 'System default microphone'
        retry_capture.echo_cancelled = True
        retry_capture.read.return_value = np.zeros(512, dtype=np.float32)

        fallback_capture = Mock()
        fallback_capture.name = 'MacBook Air Microphone'
        fallback_capture.echo_cancelled = False
        fallback_capture.read.return_value = np.full(512, .01, dtype=np.float32)

        with patch('src.voice_input.AudioCapture', side_effect=[retry_capture, fallback_capture]), \
             patch('platform.system', return_value='Darwin'), \
             contextlib.redirect_stdout(io.StringIO()):
            listener.calibrate(duration=.032)

        self.assertTrue(listener.available)
        self.assertTrue(listener.calibrated)
        self.assertIs(listener.capture, fallback_capture)
        self.assertFalse(listener.capture.echo_cancelled)

    def test_capture_splits_variable_native_chunks_without_losing_samples(self):
        import queue
        capture = AudioCapture.__new__(AudioCapture)
        capture.frames = queue.Queue()
        capture.pending = np.empty(0, dtype=np.float32)
        capture.error = None
        capture.frames.put(np.arange(100, dtype=np.float32))
        capture.frames.put(np.arange(100, 1100, dtype=np.float32))
        np.testing.assert_array_equal(capture.read(), np.arange(512))
        np.testing.assert_array_equal(capture.read(), np.arange(512, 1024))


if __name__ == '__main__':
    unittest.main()
