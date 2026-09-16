import base64
import io
import threading
import unittest
import wave
from unittest.mock import patch

import numpy as np

from src.browser_voice import BrowserVoice


def encoded_wav(seconds=.2):
    samples = np.zeros(int(16_000 * seconds), dtype='<i2')
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16_000)
        wav_file.writeframes(samples.tobytes())
    return base64.b64encode(output.getvalue()).decode('ascii')


class TestBrowserVoice(unittest.TestCase):
    def test_decodes_browser_wav(self):
        samples = BrowserVoice._decode_wav(encoded_wav())
        self.assertEqual(samples.dtype, np.float32)
        self.assertEqual(len(samples), 3200)

    def test_rejects_wrong_audio_format(self):
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(44_100)
            wav_file.writeframes(b'\0' * 20_000)
        encoded = base64.b64encode(output.getvalue()).decode('ascii')
        with self.assertRaisesRegex(ValueError, 'mono 16 kHz'):
            BrowserVoice._decode_wav(encoded)

    def test_wake_mode_ignores_speech_without_wake_phrase(self):
        voice = BrowserVoice()
        with patch.object(voice, 'transcribe', return_value='what time is it'):
            result = voice.process_turn(encoded_wav(), 'wake', ['nova'], 'Nova', 'Timi')
        self.assertTrue(result['ignored'])

    def test_wake_phrase_with_no_command_returns_acknowledgement(self):
        voice = BrowserVoice()
        with patch.object(voice, 'transcribe', return_value='nova'):
            result = voice.process_turn(encoded_wav(), 'wake', ['nova'], 'Nova', 'Timi')
        self.assertEqual(result['reply'], 'Yes, Timi?')
        self.assertTrue(result['wake'])

    def test_generated_turn_uses_cancellable_stream(self):
        voice = BrowserVoice()

        def reply(_text, cancel_event=None):
            self.assertIsInstance(cancel_event, threading.Event)
            yield 'Hello there.'

        with patch.object(voice, 'transcribe', return_value='nova hello'), \
             patch('src.browser_voice.agent.process_message_stream', side_effect=reply), \
             patch('src.browser_voice.memory.update_assistant_runtime'), \
             patch('src.browser_voice.response_interruption.begin_response', return_value=threading.Event()), \
             patch('src.browser_voice.response_interruption.finish_response'):
            result = voice.process_turn(encoded_wav(), 'wake', ['nova'], 'Nova', 'Timi')

        self.assertEqual(result['reply'], 'Hello there.')
        self.assertTrue(result['wake'])

    def test_dismissal_keywords_end_conversation(self):
        voice = BrowserVoice()
        dismissal_phrases = ['nothing', 'fine nothing', 'mean. okay, fine. nothing.', 'never mind', 'cancel', 'stop']
        for phrase in dismissal_phrases:
            with patch.object(voice, 'transcribe', return_value=phrase):
                result = voice.process_turn(encoded_wav(), 'live', ['nova'], 'Nova', 'Timi')
                self.assertTrue(result.get('end_conversation'), f"Failed for phrase: {phrase}")
                self.assertEqual(result.get('reply'), 'Alright, standing by.')


if __name__ == '__main__':
    unittest.main()
