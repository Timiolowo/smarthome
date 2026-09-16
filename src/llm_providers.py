"""
LLM Provider Abstraction Layer for Home AI Assistant.
Supports:
- Local offline LLMs (via llama-cpp-python)
- Cloud LLMs: OpenAI, Groq, Google Gemini, DeepSeek, and custom OpenAI-compatible endpoints.
"""

import json
import os
import threading
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.llm_capabilities import capabilities_for

try:
    from llama_cpp import Llama, llama_supports_gpu_offload
except ImportError:
    Llama = None


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, name: str, model: str, api_key: Optional[str] = None):
        self.name = name
        self.model = model
        self.api_key = api_key or ""
        self.available = False
        self.capabilities = capabilities_for(name, model)

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 250, temperature: float = 0.6) -> str:
        """Sends chat messages to the model and returns the text response."""
        pass

    def stream_chat(self, messages: List[Dict[str, str]], max_tokens: int = 250,
                    temperature: float = 0.6, cancel_event=None):
        """Streams text chunks from the model. Defaults to yielding the full chat response."""
        if cancel_event and cancel_event.is_set():
            return
        yield self.chat(messages, max_tokens=max_tokens, temperature=temperature)

    def is_available(self) -> bool:
        """Returns True if the provider is properly configured and ready."""
        return self.available


# =====================================================================
# 1. Local LLM Provider (llama-cpp-python / GGUF)
# =====================================================================

LLM_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "llm",
)
MODEL_3B_PATH = os.path.join(LLM_DIR, "Llama-3.2-3B-Instruct-Q4_K_M.gguf")
MODEL_1B_PATH = os.path.join(LLM_DIR, "Llama-3.2-1B-Instruct-Q4_K_M.gguf")
DEFAULT_MODEL_PATH = MODEL_3B_PATH


def get_default_local_model_path() -> str:
    if os.path.exists(MODEL_3B_PATH) and os.path.getsize(MODEL_3B_PATH) >= 2_000_000_000:
        return MODEL_3B_PATH
    return MODEL_1B_PATH


DEFAULT_MODEL_PATH = get_default_local_model_path()


class LocalLLMProvider(BaseLLMProvider):
    """Local offline inference using GGUF models via llama-cpp-python."""

    def __init__(self, model_path: Optional[str] = None):
        selected_path = model_path or get_default_local_model_path()
        model_name = os.path.basename(selected_path)
        super().__init__(name="Local LLM", model=model_name)
        self.model_path = selected_path
        self.llm = None
        self._load_lock = threading.Lock()

        if Llama is not None and os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 100_000:
            self.available = True

    def _ensure_loaded(self):
        if self.llm is not None:
            return
        with self._load_lock:
            if self.llm is not None:
                return
            if Llama is None:
                raise RuntimeError("llama-cpp-python is not installed.")
            if not os.path.exists(self.model_path):
                raise RuntimeError(f"Local model not found at {self.model_path}")

            print(f"[LLMProvider] Loading local LLM: {self.model}...")
            try:
                self.llm = Llama(
                    model_path=self.model_path,
                    n_ctx=4096,
                    n_threads=4,
                    n_gpu_layers=-1 if llama_supports_gpu_offload() else 0,
                    verbose=False,
                )
                self.available = True
                print("[LLMProvider] Local LLM loaded successfully.")
            except Exception as e:
                print(f"[LLMProvider] Failed to load local LLM ({e}).")
                self.available = False
                raise

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 250, temperature: float = 0.6) -> str:
        self._ensure_loaded()
        if not self.available or self.llm is None:
            raise RuntimeError("Local LLM model is not available.")

        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        reply = response["choices"][0]["message"]["content"].strip()
        if reply.startswith('"') and reply.endswith('"'):
            reply = reply[1:-1].strip()
        return reply

    def stream_chat(self, messages: List[Dict[str, str]], max_tokens: int = 250,
                    temperature: float = 0.6, cancel_event=None):
        self._ensure_loaded()
        if not self.available or self.llm is None:
            raise RuntimeError("Local LLM model is not available.")

        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        for chunk in response:
            if cancel_event and cancel_event.is_set():
                break
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content


# =====================================================================
# 2. OpenAI-Compatible Base Provider (Used by OpenAI, Groq, DeepSeek, etc.)
# =====================================================================

class OpenAICompatibleProvider(BaseLLMProvider):
    """Generic client for any OpenAI-compatible Chat Completions endpoint."""

    def __init__(
        self,
        name: str,
        model: str,
        endpoint: str,
        api_key: Optional[str] = None,
        timeout: int = 15,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(name=name, model=model, api_key=api_key)
        self.endpoint = endpoint
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self.available = bool(self.api_key or "localhost" in endpoint or "127.0.0.1" in endpoint)

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 250, temperature: float = 0.6) -> str:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SmartHome-Assistant/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self.extra_headers)

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data["choices"][0]["message"]["content"].strip()
                if reply.startswith('"') and reply.endswith('"'):
                    reply = reply[1:-1].strip()
                return reply
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"[{self.name}] API HTTP error {e.code}: {error_body}")
            raise RuntimeError(f"{self.name} API error (HTTP {e.code})") from e
        except Exception as e:
            print(f"[{self.name}] Request failed: {e}")
            raise RuntimeError(f"{self.name} request failed: {e}") from e

    def stream_chat(self, messages: List[Dict[str, str]], max_tokens: int = 250,
                    temperature: float = 0.6, cancel_event=None):
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SmartHome-Assistant/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self.extra_headers)

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for line in resp:
                    if cancel_event and cancel_event.is_set():
                        break
                    line_str = line.decode("utf-8").strip()
                    if not line_str or line_str.startswith(":"):
                        continue
                    if line_str.startswith("data: "):
                        data_str = line_str[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"[{self.name}] API HTTP error {e.code}: {error_body}")
            raise RuntimeError(f"{self.name} API error (HTTP {e.code})") from e
        except Exception as e:
            print(f"[{self.name}] Stream request failed: {e}")
            raise RuntimeError(f"{self.name} stream request failed: {e}") from e


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI API Provider (GPT-4o, GPT-4o-mini, etc.)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        model_name = model or "gpt-4o-mini"
        super().__init__(
            name="OpenAI",
            model=model_name,
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key=key,
        )


class GroqProvider(OpenAICompatibleProvider):
    """Groq Cloud API Provider (Ultra-fast Llama-3, Mixtral)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        key = api_key or os.getenv("GROQ_API_KEY", "")
        model_name = model or "llama-3.3-70b-versatile"
        super().__init__(
            name="Groq",
            model=model_name,
            endpoint="https://api.groq.com/openai/v1/chat/completions",
            api_key=key,
        )


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek API Provider (DeepSeek-V3 / DeepSeek-R1)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        model_name = model or "deepseek-chat"
        super().__init__(
            name="DeepSeek",
            model=model_name,
            endpoint="https://api.deepseek.com/chat/completions",
            api_key=key,
        )


class CustomOpenAIProvider(OpenAICompatibleProvider):
    """Custom OpenAI-compatible provider (Ollama, OpenRouter, Together, LM Studio, etc.)."""

    def __init__(self, base_url: str, api_key: Optional[str] = None, model: Optional[str] = None):
        endpoint = base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            if not endpoint.endswith("/v1"):
                endpoint = f"{endpoint}/v1"
            endpoint = f"{endpoint}/chat/completions"

        key = api_key or os.getenv("CUSTOM_LLM_API_KEY", "")
        model_name = model or "default"
        super().__init__(
            name="Custom LLM",
            model=model_name,
            endpoint=endpoint,
            api_key=key,
        )


# =====================================================================
# 3. Google Gemini Provider
# =====================================================================

class GeminiProvider(BaseLLMProvider):
    """Google Gemini REST API Provider."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, timeout: int = 15):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        model_name = model or "gemini-2.5-flash"
        super().__init__(name="Google Gemini", model=model_name, api_key=key)
        self.timeout = timeout
        self.available = bool(self.api_key)

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 250, temperature: float = 0.6) -> str:
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured.")

        # Extract system prompt and user/assistant messages
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "user" if role == "user" else "model"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SmartHome-Assistant/1.0",
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError("No candidates returned from Gemini.")

                parts = candidates[0].get("content", {}).get("parts", [])
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                reply = "".join(text_parts).strip()
                if reply.startswith('"') and reply.endswith('"'):
                    reply = reply[1:-1].strip()
                return reply
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"[Gemini] Model {self.model} returned HTTP {e.code}: {error_body}")
            raise RuntimeError(f"Gemini API error (HTTP {e.code})") from e
        except Exception as e:
            print(f"[Gemini] Request with {self.model} failed: {e}")
            raise RuntimeError(f"Gemini request failed: {e}") from e

    def stream_chat(self, messages: List[Dict[str, str]], max_tokens: int = 250,
                    temperature: float = 0.6, cancel_event=None):
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured.")

        system_instruction = None
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "user" if role == "user" else "model"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SmartHome-Assistant/1.0",
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for line in resp:
                    if cancel_event and cancel_event.is_set():
                        break
                    line_str = line.decode("utf-8").strip()
                    if not line_str or line_str.startswith(":"):
                        continue
                    if line_str.startswith("data: "):
                        data_str = line_str[6:].strip()
                        try:
                            chunk = json.loads(data_str)
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    text = p.get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            continue
        except Exception:
            # Fallback to single-turn chat if streaming endpoint encounters any issues
            if not (cancel_event and cancel_event.is_set()):
                yield self.chat(messages, max_tokens=max_tokens, temperature=temperature)



# =====================================================================
# Factory Function
# =====================================================================

def get_llm_provider(
    provider_type: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> BaseLLMProvider:
    """
    Factory function to create and return the configured LLM provider.
    Supports provider_type: 'local', 'openai', 'groq', 'deepseek', 'gemini', 'custom'.
    """
    p_type = (provider_type or "local").strip().lower()

    if p_type == "openai":
        return OpenAIProvider(api_key=api_key, model=model)
    elif p_type == "groq":
        return GroqProvider(api_key=api_key, model=model)
    elif p_type == "deepseek":
        return DeepSeekProvider(api_key=api_key, model=model)
    elif p_type in ("gemini", "google"):
        return GeminiProvider(api_key=api_key, model=model)
    elif p_type == "custom" and base_url:
        return CustomOpenAIProvider(base_url=base_url, api_key=api_key, model=model)
    else:
        # Default: Local LLM
        return LocalLLMProvider(model_path=model if (model and os.path.exists(model)) else None)
