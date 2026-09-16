"""Capability declarations for LLM provider adapters.

Keep provider-specific feature checks here so voice orchestration and UI code do
not need to know model naming rules or API limitations.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LLMCapabilities:
    streaming: bool = True
    interruption: bool = True
    native_web_search: bool = False
    visit_website: bool = False
    tool_calling: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def capabilities_for(provider_name: str, model: str) -> LLMCapabilities:
    """Return only features supported by the adapter/model combination in use."""
    provider = (provider_name or "").strip().lower()
    model_name = (model or "").strip().lower()

    if provider == "groq":
        compound = model_name in {"groq/compound", "groq/compound-mini"}
        return LLMCapabilities(
            native_web_search=compound,
            visit_website=compound,
            tool_calling=True,
        )
    if provider == "google gemini":
        return LLMCapabilities(native_web_search=True, visit_website=True, tool_calling=True)
    if provider in {"openai", "deepseek", "custom llm"}:
        # This project currently uses their Chat Completions-compatible adapter.
        # OpenAI native web search requires a separate Responses API adapter.
        return LLMCapabilities(tool_calling=True)
    return LLMCapabilities(tool_calling=False)
