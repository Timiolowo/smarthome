"""
Unit tests for duplex voice interruption, sentence streaming, and context tracking.
"""

import json
import os
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from src.agent import HomeAgent
from src.audio_capabilities import interruption_capabilities
from src.brain import Brain, split_sentences
from src.config import AppConfig
from src.interruption import ResponseInterruption
from src.llm_providers import BaseLLMProvider
from src.voice_output import SoundDevicePlayback, Speaker, speak_stream


class TestVoiceInterruption(unittest.TestCase):

    def test_response_interruption_uses_a_fresh_event_per_turn(self):
        controller = ResponseInterruption()
        first = controller.begin_response()
        controller.interrupt()
        second = controller.begin_response()

        self.assertTrue(first.is_set())
        self.assertFalse(second.is_set())
        self.assertTrue(controller.is_active())
        controller.finish_response(second)
        self.assertFalse(controller.is_active())

    def test_interruption_capabilities_only_enable_voice_with_echo_cancellation(self):
        with patch('src.audio_capabilities.platform.system', return_value='Windows'):
            standard = interruption_capabilities(False)
            echo_cancelled = interruption_capabilities(True)

        self.assertEqual(standard['platform'], 'windows')
        self.assertTrue(standard['web_ui'])
        self.assertTrue(standard['keyboard'])
        self.assertFalse(standard['voice_barge_in'])
        self.assertTrue(echo_cancelled['voice_barge_in'])

    def test_cross_platform_speaker_stop_stops_audio_backends(self):
        speaker = Speaker.__new__(Speaker)
        speaker.native_capture = None
        speaker.current_process = None
        speaker._engine = MagicMock()

        with patch('src.voice_output.sd') as mock_sd:
            speaker.stop()

        mock_sd.stop.assert_called_once()
        speaker._engine.stop.assert_called_once()

    def test_sounddevice_playback_reports_active_state(self):
        with patch('src.voice_output.sd') as mock_sd:
            mock_sd.get_stream.return_value.active = True
            self.assertIsNone(SoundDevicePlayback().poll())
            mock_sd.get_stream.return_value.active = False
            self.assertEqual(SoundDevicePlayback().poll(), 0)

    def test_split_sentences_basic(self):
        """Test sentence splitting on common sentence boundaries."""
        tokens = ["Hello ", "world. ", "How are ", "you today? ", "I am ", "doing well!"]
        sentences = list(split_sentences(tokens))
        self.assertEqual(sentences, ["Hello world.", "How are you today?", "I am doing well!"])

    def test_split_sentences_abbreviations(self):
        """Test that abbreviations like Dr., Mr., e.g. are not prematurely split."""
        tokens = ["Hello, Dr. ", "Smith. ", "Please meet Mr. ", "Jones at noon."]
        sentences = list(split_sentences(tokens))
        self.assertEqual(sentences, ["Hello, Dr. Smith.", "Please meet Mr. Jones at noon."])

    def test_split_sentences_newlines(self):
        """Test splitting on newlines and trailing text without end punctuation."""
        tokens = ["First line\n", "Second line\n\n", "Third line without period"]
        sentences = list(split_sentences(tokens))
        self.assertEqual(sentences, ["First line", "Second line", "Third line without period"])

    def test_split_sentences_cancellation(self):
        """Test that setting cancel_event stops sentence streaming immediately."""
        cancel_event = threading.Event()

        def token_gen():
            yield "Sentence one. "
            cancel_event.set()
            yield "Sentence two. "
            yield "Sentence three. "

        sentences = list(split_sentences(token_gen(), cancel_event=cancel_event))
        self.assertEqual(sentences, ["Sentence one."])

    def test_brain_stream_chat_and_interruption_context(self):
        """Test streaming from Brain, recording interruption, and subsequent context formatting."""
        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.name = "MockProvider"
        mock_provider.model = "mock-20b"
        mock_provider.is_available.return_value = True

        def mock_stream(messages, **kwargs):
            yield "I found two "
            yield "flights for Friday. "
            yield "Would you like "
            yield "morning or evening?"

        mock_provider.stream_chat.side_effect = mock_stream

        cfg = AppConfig(llm_provider="custom")
        brain = Brain(provider=mock_provider, config=cfg)

        # 1. First user turn streams sentences
        sentences = list(brain.stream_chat("Find flights for Friday"))
        self.assertEqual(sentences, ["I found two flights for Friday.", "Would you like morning or evening?"])

        # 2. Suppose user interrupted while assistant was speaking "I found two flights for Friday."
        brain.record_interruption("I found two flights for Friday.")
        self.assertTrue(brain.interrupted_turn)
        self.assertIn("... [interrupted]", brain.history[-1]["content"])

        # 3. User says: "No, I meant Saturday."
        def mock_stream_turn2(messages, **kwargs):
            # Verify the last user message includes the interruption context
            user_msg = messages[-1]["content"]
            self.assertIn("Previous response was interrupted", user_msg)
            self.assertIn('User now says: "No, I meant Saturday."', user_msg)
            yield "Got it. Searching for Saturday flights instead."

        mock_provider.stream_chat.side_effect = mock_stream_turn2
        reply_turn2 = list(brain.stream_chat("No, I meant Saturday."))
        self.assertEqual(" ".join(reply_turn2), "Got it. Searching for Saturday flights instead.")
        self.assertFalse(brain.interrupted_turn)

    def test_agent_process_message_stream_tool(self):
        """Test agent returns instant response for tool commands."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            history_file = f.name
        try:
            agent = HomeAgent(history_file=history_file)
            results = list(agent.process_message_stream("Set a timer for 10 minutes"))
            self.assertEqual(len(results), 1)
            self.assertTrue(any(w in results[0].lower() for w in ("timer", "alarm")))
        finally:
            if os.path.exists(history_file):
                os.unlink(history_file)

    def test_agent_record_interruption(self):
        """Test agent saves partial spoken text to history file on interruption."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            history_file = f.name
        try:
            agent = HomeAgent(history_file=history_file)
            agent._save_turn("user", "Tell me about space")
            agent._save_turn("assistant", "Space is vast and fascinating")

            agent.record_interruption("Space is vast")
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
            self.assertEqual(history[-1]["content"], "Space is vast... [interrupted]")
        finally:
            if os.path.exists(history_file):
                os.unlink(history_file)

    def test_speak_stream_interruption(self):
        """Test speak_stream stops speaker and sets cancel_event when interrupted."""
        cancel_event = threading.Event()
        mock_listener = MagicMock()
        mock_speaker = MagicMock()

        # Simulate: sentence 1 plays fine, sentence 2 is interrupted
        mock_speaker.speak.side_effect = [False, True]

        sentences = ["First sentence.", "Second sentence.", "Third sentence."]

        with patch("src.voice_output.speaker", mock_speaker):
            interrupted, spoken = speak_stream(
                sentences,
                listener=mock_listener,
                interruptible=True,
                cancel_event=cancel_event,
            )

        self.assertTrue(interrupted)
        self.assertTrue(cancel_event.is_set())
        # First sentence played, second sentence was interrupted
        self.assertEqual(spoken, "First sentence.")
        self.assertEqual(mock_speaker.speak.call_count, 2)

    def test_external_cancellation_is_reported_when_stream_ends(self):
        cancel_event = threading.Event()

        def sentences():
            yield "First sentence."
            cancel_event.set()

        with patch("src.voice_output.speaker") as mock_speaker:
            mock_speaker.speak.return_value = False
            interrupted, spoken = speak_stream(sentences(), cancel_event=cancel_event)

        self.assertTrue(interrupted)
        self.assertEqual(spoken, "First sentence.")

    def test_speak_stream_closes_provider_generator_on_interruption(self):
        cancel_event = threading.Event()
        closed = threading.Event()

        def sentence_stream():
            try:
                yield "A response that is interrupted."
                yield "This sentence must never play."
            finally:
                closed.set()

        with patch("src.voice_output.speaker") as mock_speaker:
            mock_speaker.speak.return_value = True
            interrupted, _ = speak_stream(
                sentence_stream(),
                listener=MagicMock(),
                cancel_event=cancel_event,
            )

        self.assertTrue(interrupted)
        self.assertTrue(cancel_event.is_set())
        self.assertTrue(closed.is_set())


if __name__ == "__main__":
    unittest.main()
