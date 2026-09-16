"""
Brain module managing conversation context, memory injection, and LLM execution.
Delegates model inference to modular providers defined in src.llm_providers.
"""

import os
import re
from typing import List, Optional

from src.config import AppConfig, load_config
from src.llm_providers import (
    BaseLLMProvider,
    LocalLLMProvider,
    get_default_local_model_path,
    get_llm_provider,
    MODEL_3B_PATH,
    MODEL_1B_PATH,
    DEFAULT_MODEL_PATH,
)
from src.memory import memory


def split_sentences(token_generator, cancel_event=None):
    """Accumulates streamed tokens and yields cleanly completed sentences."""
    buffer = ""
    sentence_end_re = re.compile(r'([.?!]+[\s\n]+|\n+)')
    abbreviations = ("mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "e.g.", "i.e.", "vs.", "etc.")

    for token in token_generator:
        if cancel_event and cancel_event.is_set():
            return
        buffer += token

        pos = 0
        while True:
            match = sentence_end_re.search(buffer, pos)
            if not match:
                break
            end_pos = match.end()
            candidate = buffer[:end_pos].strip()

            candidate_lower = candidate.lower()
            if any(candidate_lower.endswith(abbr) for abbr in abbreviations):
                pos = match.end()
                continue

            if candidate:
                yield candidate
            buffer = buffer[end_pos:]
            pos = 0

    if cancel_event and cancel_event.is_set():
        return

    remaining = buffer.strip()
    if remaining:
        yield remaining


class Brain:
    """Conversational engine managing memory, prompt building, and LLM inference."""

    def __init__(self, provider: Optional[BaseLLMProvider] = None, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.provider: BaseLLMProvider = provider or self._init_provider(self.config)
        self.history: List[dict] = []
        self.interrupted_turn: bool = False
        self.reset_history()

    def _init_provider(self, cfg: AppConfig) -> BaseLLMProvider:
        return get_llm_provider(
            provider_type=cfg.llm_provider,
            api_key=cfg.llm_api_key,
            model=cfg.llm_model,
            base_url=cfg.llm_base_url,
        )

    def reload(self, config: Optional[AppConfig] = None) -> None:
        """Reloads the LLM provider based on updated configuration."""
        self.config = config or load_config()
        self.provider = self._init_provider(self.config)
        self.reset_history()
        print(f"[Brain] Reloaded LLM provider: {self.provider.name} ({self.provider.model})")

    @property
    def available(self) -> bool:
        return self.provider.is_available()

    @property
    def provider_name(self) -> str:
        return self.provider.name

    @property
    def model_name(self) -> str:
        return self.provider.model

    @property
    def provider_capabilities(self) -> dict:
        return self.provider.capabilities.to_dict()

    @property
    def model_path(self) -> str:
        """Backward compatibility property for local model path references."""
        if isinstance(self.provider, LocalLLMProvider):
            return self.provider.model_path
        return self.provider.model

    def reset_history(self) -> None:
        """Resets conversational history and re-injects current memory context."""
        system_prompt = memory.get_llm_system_prompt()
        self.history = [{"role": "system", "content": system_prompt}]
        self.interrupted_turn = False

    def record_interruption(self, partial_spoken_text: str) -> None:
        """Marks that the assistant's ongoing response was cut off by user speech."""
        self.interrupted_turn = True
        cut_text = (partial_spoken_text or "").strip()
        interrupted_msg = f"{cut_text}... [interrupted]" if cut_text else "[interrupted before speaking]"
        if self.history and self.history[-1].get("role") == "assistant":
            self.history[-1]["content"] = interrupted_msg
        else:
            self.history.append({"role": "assistant", "content": interrupted_msg})

    def stream_chat(self, user_text: str, cancel_event=None):
        """
        Streams response sentences one-by-one from the LLM provider.
        Checks cancel_event on every chunk for immediate abort on user interruption.
        """
        if not self.available:
            yield "My conversation model is unavailable. You can still ask me to set timers, manage lights, or remember a fact."
            return

        # Dynamically refresh system prompt on every turn with current clock and state
        system_msg = {"role": "system", "content": memory.get_llm_system_prompt()}
        if self.history and self.history[0].get("role") == "system":
            self.history[0] = system_msg
        else:
            self.history.insert(0, system_msg)

        # Keep history within context limit (system prompt + recent 8 turns)
        if len(self.history) > 12:
            self.history = [self.history[0]] + self.history[-8:]

        # Annotate user prompt if the previous turn was interrupted
        user_content = user_text
        if self.interrupted_turn:
            user_content = f'Previous response was interrupted. User now says: "{user_text}"'
            self.interrupted_turn = False

        self.history.append({"role": "user", "content": user_content})

        is_story = bool(re.search(
            r'\b(story|tale|legend|fable|chronicle|history|narrative|full\s+story|beginning to (the )?end|whole thing)\b',
            user_text,
            re.I,
        ))
        is_detailed = bool(re.search(
            r'\b(detail|detailed|explain|explanation|list|steps|reasons|breakdown|elaborate|describe|tell me about|tell me more|continue)\b',
            user_text,
            re.I,
        ))
        tokens_limit = 750 if is_story else (350 if is_detailed else 120)

        assistant_turn = {"role": "assistant", "content": ""}
        self.history.append(assistant_turn)
        accumulated = []

        try:
            raw_stream = self.provider.stream_chat(
                messages=self.history[:-1],
                max_tokens=tokens_limit,
                temperature=0.6,
                cancel_event=cancel_event,
            )
            for sentence in split_sentences(raw_stream, cancel_event=cancel_event):
                if cancel_event and cancel_event.is_set():
                    break
                accumulated.append(sentence)
                assistant_turn["content"] = " ".join(accumulated).strip()
                yield sentence
        except Exception as e:
            err_msg = str(e)
            print(f"[Brain] Stream inference error ({err_msg}), falling back...")
            if not accumulated:
                fallback = err_msg if ("rate limit" in err_msg.lower() or "quota" in err_msg.lower() or "429" in err_msg) else f"Model error: {err_msg}"
                assistant_turn["content"] = fallback
                yield fallback
        finally:
            if not assistant_turn["content"]:
                # If nothing was yielded or immediately canceled
                self.history.pop()

    def chat(self, user_text: str) -> str:
        """Performs continuous multi-turn dialogue with conversational memory."""
        if not self.available:
            return "My conversation model is unavailable. You can still ask me to set timers, manage lights, or remember a fact."

        # Dynamically refresh system prompt on every turn with current clock and state
        system_msg = {"role": "system", "content": memory.get_llm_system_prompt()}
        if self.history and self.history[0].get("role") == "system":
            self.history[0] = system_msg
        else:
            self.history.insert(0, system_msg)

        # Keep history within context limit (system prompt + recent 8 turns)
        if len(self.history) > 12:
            self.history = [self.history[0]] + self.history[-8:]

        # Annotate user prompt if the previous turn was interrupted
        user_content = user_text
        if self.interrupted_turn:
            user_content = f'Previous response was interrupted. User now says: "{user_text}"'
            self.interrupted_turn = False

        self.history.append({"role": "user", "content": user_content})

        is_story = bool(re.search(
            r'\b(story|tale|legend|fable|chronicle|history|narrative|full\s+story|beginning to (the )?end|whole thing)\b',
            user_text,
            re.I,
        ))
        is_detailed = bool(re.search(
            r'\b(detail|detailed|explain|explanation|list|steps|reasons|breakdown|elaborate|describe|tell me about|tell me more|continue)\b',
            user_text,
            re.I,
        ))
        tokens_limit = 750 if is_story else (350 if is_detailed else 120)

        try:
            reply = self.provider.chat(
                messages=self.history,
                max_tokens=tokens_limit,
                temperature=0.6,
            )
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            err_msg = str(e)
            print(f"[Brain] Inference error ({err_msg}), falling back...")
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()  # Remove unanswered turn
            if "rate limit" in err_msg.lower() or "quota" in err_msg.lower() or "429" in err_msg:
                return err_msg
            return f"Model error: {err_msg}"

    def generate_response(self, user_text: str) -> str:
        """Single-turn wrapper that starts a fresh conversation."""
        self.reset_history()
        return self.chat(user_text)


# Backwards compatibility alias
LocalBrain = Brain

# Global singleton
brain = Brain()
