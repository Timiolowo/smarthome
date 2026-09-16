"""
Unit tests for modular LLM Providers (Local, OpenAI, Groq, DeepSeek, Gemini, Custom).
"""

import io
import json
import threading
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from src.config import AppConfig
from src.brain import Brain
from src.llm_providers import (
    BaseLLMProvider,
    CustomOpenAIProvider,
    DeepSeekProvider,
    GeminiProvider,
    GroqProvider,
    LocalLLMProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    get_llm_provider,
)
from src.llm_capabilities import capabilities_for


class MockHTTPResponse:
    def __init__(self, data: dict, status: int = 200):
        self.data = json.dumps(data).encode("utf-8")
        self.status = status

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestLLMProviders(unittest.TestCase):

    def test_factory_defaults(self):
        """Test factory returns appropriate provider types."""
        p_local = get_llm_provider("local")
        self.assertIsInstance(p_local, LocalLLMProvider)
        self.assertEqual(p_local.name, "Local LLM")

        p_openai = get_llm_provider("openai", api_key="sk-test", model="gpt-4o")
        self.assertIsInstance(p_openai, OpenAIProvider)
        self.assertEqual(p_openai.model, "gpt-4o")
        self.assertTrue(p_openai.is_available())

        p_groq = get_llm_provider("groq", api_key="gsk-test")
        self.assertIsInstance(p_groq, GroqProvider)
        self.assertEqual(p_groq.model, "llama-3.3-70b-versatile")
        self.assertTrue(p_groq.is_available())

        p_deepseek = get_llm_provider("deepseek", api_key="dsk-test")
        self.assertIsInstance(p_deepseek, DeepSeekProvider)
        self.assertEqual(p_deepseek.model, "deepseek-chat")
        self.assertTrue(p_deepseek.is_available())

        p_gemini = get_llm_provider("gemini", api_key="AIza-test")
        self.assertIsInstance(p_gemini, GeminiProvider)
        self.assertEqual(p_gemini.model, "gemini-2.5-flash")
        self.assertTrue(p_gemini.is_available())

        p_custom = get_llm_provider("custom", base_url="http://localhost:11434", model="mistral")
        self.assertIsInstance(p_custom, CustomOpenAIProvider)
        self.assertEqual(p_custom.endpoint, "http://localhost:11434/v1/chat/completions")

    def test_provider_capabilities_are_model_specific(self):
        compound = capabilities_for("Groq", "groq/compound")
        regular_groq = capabilities_for("Groq", "llama-3.3-70b-versatile")
        openai_chat = capabilities_for("OpenAI", "gpt-4o-mini")

        self.assertTrue(compound.native_web_search)
        self.assertTrue(compound.visit_website)
        self.assertFalse(regular_groq.native_web_search)
        self.assertTrue(openai_chat.interruption)
        self.assertFalse(openai_chat.native_web_search)

    @patch("urllib.request.urlopen")
    def test_openai_provider_chat(self, mock_urlopen):
        """Test OpenAI Chat completions request & response parsing."""
        mock_urlopen.return_value = MockHTTPResponse({
            "choices": [{"message": {"content": "Hello from OpenAI!"}}]
        })

        provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")
        messages = [{"role": "user", "content": "Hi"}]
        reply = provider.chat(messages)

        self.assertEqual(reply, "Hello from OpenAI!")
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.openai.com/v1/chat/completions")
        self.assertIn("Bearer test-key", req.headers["Authorization"])

    @patch("urllib.request.urlopen")
    def test_groq_provider_chat(self, mock_urlopen):
        """Test Groq Chat request."""
        mock_urlopen.return_value = MockHTTPResponse({
            "choices": [{"message": {"content": "Ultra-fast response from Groq!"}}]
        })

        provider = GroqProvider(api_key="gsk-test")
        reply = provider.chat([{"role": "user", "content": "How fast are you?"}])

        self.assertEqual(reply, "Ultra-fast response from Groq!")
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.groq.com/openai/v1/chat/completions")

    @patch("urllib.request.urlopen")
    def test_deepseek_provider_chat(self, mock_urlopen):
        """Test DeepSeek API request."""
        mock_urlopen.return_value = MockHTTPResponse({
            "choices": [{"message": {"content": "DeepSeek reasoning output."}}]
        })

        provider = DeepSeekProvider(api_key="dsk-test")
        reply = provider.chat([{"role": "user", "content": "Solve this puzzle."}])

        self.assertEqual(reply, "DeepSeek reasoning output.")
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.deepseek.com/chat/completions")

    @patch("urllib.request.urlopen")
    def test_gemini_provider_chat(self, mock_urlopen):
        """Test Google Gemini REST API request and message transformation."""
        mock_urlopen.return_value = MockHTTPResponse({
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello from Gemini!"}],
                    "role": "model",
                }
            }]
        })

        provider = GeminiProvider(api_key="AIzaSyTestKey", model="gemini-1.5-flash")
        messages = [
            {"role": "system", "content": "You are Nova."},
            {"role": "user", "content": "Tell me a joke."},
        ]
        reply = provider.chat(messages)

        self.assertEqual(reply, "Hello from Gemini!")
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertIn("generativelanguage.googleapis.com", req.full_url)
        self.assertIn("key=AIzaSyTestKey", req.full_url)

        # Inspect payload
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "You are Nova.")
        self.assertEqual(payload["contents"][0]["role"], "user")
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "Tell me a joke.")

    def test_brain_with_mock_provider(self):
        """Test Brain integration with a provider."""
        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.name = "MockProvider"
        mock_provider.model = "mock-model"
        mock_provider.is_available.return_value = True
        mock_provider.chat.return_value = "Mocked answer for user."

        cfg = AppConfig(llm_provider="openai")
        brain = Brain(provider=mock_provider, config=cfg)

        self.assertTrue(brain.available)
        self.assertEqual(brain.provider_name, "MockProvider")
        self.assertEqual(brain.model_name, "mock-model")

        reply = brain.chat("What is the temperature today?")
        self.assertEqual(reply, "Mocked answer for user.")
        mock_provider.chat.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_openai_stream_chat(self, mock_urlopen):
        """Test streaming SSE parsing for OpenAICompatibleProvider."""
        sse_lines = [
            b'data: {"choices": [{"delta": {"content": "Hello "}}]}\n',
            b'data: {"choices": [{"delta": {"content": "there, "}}]}\n',
            b'data: {"choices": [{"delta": {"content": "human."}}]}\n',
            b'data: [DONE]\n',
        ]
        mock_resp = MagicMock()
        mock_resp.__iter__.return_value = iter(sse_lines)
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
        mock_urlopen.return_value = mock_resp

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        chunks = list(provider.stream_chat([{"role": "user", "content": "hi"}]))
        self.assertEqual("".join(chunks), "Hello there, human.")

    @patch("urllib.request.urlopen")
    def test_openai_stream_honors_cancellation(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__iter__.return_value = iter([
            b'data: {"choices": [{"delta": {"content": "First "}}]}\n',
            b'data: {"choices": [{"delta": {"content": "second"}}]}\n',
            b'data: [DONE]\n',
        ])
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        cancel_event = threading.Event()

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        stream = provider.stream_chat([{"role": "user", "content": "hi"}], cancel_event=cancel_event)
        self.assertEqual(next(stream), "First ")
        cancel_event.set()
        self.assertEqual(list(stream), [])
        mock_resp.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
